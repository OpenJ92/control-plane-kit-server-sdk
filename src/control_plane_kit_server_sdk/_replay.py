"""Bounded process-local replay for admitted node-control APPLY requests."""

from __future__ import annotations

from dataclasses import dataclass
import json
from threading import Condition, Lock, get_ident
import time
from typing import Callable

from control_plane_kit_core import (
    NodeControlCommandRequest,
    NodeControlFailed,
    NodeControlOperation,
    NodeControlRejected,
    NodeControlResultCodec,
    NodeControlTransitionSucceeded,
)
from control_plane_kit_core.node_control import (
    MAX_NODE_CONTROL_PAYLOAD_BYTES,
    MAX_WORKLOAD_NODE_CONTROL_GRANT_LIFETIME_SECONDS,
)


_MAX_CAPACITY = 4096
_MAX_CLOCK_NS = 2**63 - 1
_RETENTION_NS = MAX_WORKLOAD_NODE_CONTROL_GRANT_LIFETIME_SECONDS * 1_000_000_000
_RESULT_TYPES = (
    NodeControlTransitionSucceeded,
    NodeControlRejected,
    NodeControlFailed,
)


class _NodeControlReplayError(RuntimeError):
    """Base category for bounded replay-control failures."""

    _MESSAGE = "node-control replay failed"

    def __init__(self) -> None:
        super().__init__(self._MESSAGE)


class _NodeControlReplayContractError(_NodeControlReplayError):
    _MESSAGE = "node-control replay call is invalid"


class _NodeControlReplayConflict(_NodeControlReplayError):
    _MESSAGE = "node-control replay intent conflicts"


class _NodeControlReplayCapacityExhausted(_NodeControlReplayError):
    _MESSAGE = "node-control replay capacity is exhausted"


class _NodeControlReplayReentry(_NodeControlReplayError):
    _MESSAGE = "node-control replay owner cannot re-enter"


@dataclass(frozen=True, slots=True)
class _InFlight:
    digest: str
    owner_thread_id: int


@dataclass(frozen=True, slots=True)
class _Terminal:
    digest: str
    result_bytes: bytes
    completed_at_ns: int | None
    retention_anchor_pending: bool


_Entry = _InFlight | _Terminal
_ApplyResult = NodeControlTransitionSucceeded | NodeControlRejected | NodeControlFailed


def _serialize_terminal_descriptor(descriptor: object) -> bytes:
    """Encode one private compact-JSON descriptor within the core byte bound."""
    failed = type(descriptor) is not dict
    encoded = b""
    if not failed:
        try:
            text = json.dumps(
                descriptor,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            encoded = text.encode("utf-8", errors="strict")
        except Exception:
            failed = True
    if failed or not 1 <= len(encoded) <= MAX_NODE_CONTROL_PAYLOAD_BYTES:
        raise ValueError("node-control replay terminal is invalid")
    return encoded


def _decode_terminal(
    terminal_bytes: bytes,
    result_codec: NodeControlResultCodec,
    request_id: str,
) -> _ApplyResult:
    failed = False
    decoded: object = None
    try:
        text = terminal_bytes.decode("utf-8", errors="strict")
        descriptor = json.loads(text)
        decoded = result_codec.decode(descriptor)
    except Exception:
        failed = True
    if (
        failed
        or type(decoded) not in _RESULT_TYPES
        or decoded.operation is not NodeControlOperation.APPLY_COMMAND
        or type(decoded.request_id) is not str
        or decoded.request_id != request_id
    ):
        raise ValueError("node-control replay terminal is invalid")
    return decoded


def _normalize_terminal(
    result: object,
    result_codec: NodeControlResultCodec,
    request_id: str,
) -> bytes:
    failed = type(result) not in _RESULT_TYPES
    descriptor: object = None
    if not failed:
        try:
            descriptor = result_codec.encode(result)
        except Exception:
            failed = True
    if failed:
        raise ValueError("node-control replay terminal is invalid")
    terminal_bytes = _serialize_terminal_descriptor(descriptor)
    _decode_terminal(terminal_bytes, result_codec, request_id)
    return terminal_bytes


class _ProcessLocalNodeControlReplay:
    """Coordinate bounded replay within one synchronous route installation."""

    __slots__ = ("_capacity", "_clock_ns", "_condition", "_entries")

    def __init__(
        self,
        *,
        capacity: int = 1024,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        if (
            type(capacity) is not int
            or not 1 <= capacity <= _MAX_CAPACITY
            or not callable(clock_ns)
        ):
            raise _NodeControlReplayContractError()
        self._capacity = capacity
        self._clock_ns = clock_ns
        self._condition = Condition(Lock())
        self._entries: dict[str, _Entry] = {}

    def execute(
        self,
        request: NodeControlCommandRequest,
        *,
        result_codec: NodeControlResultCodec,
        dispatch: Callable[[], object],
    ) -> _ApplyResult:
        prepared = self._prepare(request, result_codec, dispatch)
        if prepared is None:
            raise _NodeControlReplayContractError()
        key, digest, fallback_bytes = prepared

        initial_ns = self._read_clock()
        if initial_ns is None:
            raise _NodeControlReplayContractError()

        owner_thread_id = get_ident()
        terminal_bytes: bytes | None = None
        owns_reservation = False
        with self._condition:
            self._prune(initial_ns)
            while True:
                entry = self._entries.get(key)
                if entry is None:
                    if len(self._entries) == self._capacity:
                        raise _NodeControlReplayCapacityExhausted()
                    self._entries[key] = _InFlight(digest, owner_thread_id)
                    owns_reservation = True
                    break
                if entry.digest != digest:
                    raise _NodeControlReplayConflict()
                if type(entry) is _Terminal:
                    terminal_bytes = entry.result_bytes
                    break
                if entry.owner_thread_id == owner_thread_id:
                    raise _NodeControlReplayReentry()
                self._condition.wait()

        if not owns_reservation:
            return self._decode_or_fallback(
                terminal_bytes,
                fallback_bytes,
                result_codec,
                request.request_id,
            )

        control_exception: BaseException | None = None
        publish_bytes = fallback_bytes
        unprunable = False
        try:
            result = dispatch()
            publish_bytes = _normalize_terminal(
                result,
                result_codec,
                request.request_id,
            )
        except BaseException as error:
            if not isinstance(error, Exception):
                control_exception = error
                unprunable = True

        retention_anchor_pending = False
        if control_exception is None:
            try:
                completion_candidate = self._clock_ns()
            except BaseException as error:
                completion_candidate = None
                if not isinstance(error, Exception):
                    control_exception = error
            if (
                type(completion_candidate) is int
                and initial_ns <= completion_candidate <= _MAX_CLOCK_NS
            ):
                retention_anchor_pending = True
            else:
                publish_bytes = fallback_bytes
                unprunable = True

        with self._condition:
            entry = self._entries.get(key)
            if (
                type(entry) is not _InFlight
                or entry.digest != digest
                or entry.owner_thread_id != owner_thread_id
            ):
                raise RuntimeError("node-control replay reservation was lost")
            self._entries[key] = _Terminal(
                digest=digest,
                result_bytes=publish_bytes,
                completed_at_ns=None,
                retention_anchor_pending=(
                    retention_anchor_pending and not unprunable
                ),
            )
            self._condition.notify_all()

        if control_exception is not None:
            raise control_exception
        return self._decode_or_fallback(
            publish_bytes,
            fallback_bytes,
            result_codec,
            request.request_id,
        )

    def _prepare(
        self,
        request: object,
        result_codec: object,
        dispatch: object,
    ) -> tuple[str, str, bytes] | None:
        if (
            type(request) is not NodeControlCommandRequest
            or request.operation is not NodeControlOperation.APPLY_COMMAND
            or type(request.request_id) is not str
            or type(request.idempotency_key) is not str
            or type(result_codec) is not NodeControlResultCodec
            or not callable(dispatch)
        ):
            return None
        failed = False
        digest_value = ""
        fallback_bytes = b""
        try:
            digest = request.canonical_digest()
            digest_value = digest.value
            fallback_bytes = _normalize_terminal(
                NodeControlFailed(
                    request_id=request.request_id,
                    operation=NodeControlOperation.APPLY_COMMAND,
                ),
                result_codec,
                request.request_id,
            )
        except Exception:
            failed = True
        if failed or type(digest_value) is not str:
            return None
        return request.idempotency_key, digest_value, fallback_bytes

    def _read_clock(self) -> int | None:
        failed = False
        value: object = None
        try:
            value = self._clock_ns()
        except Exception:
            failed = True
        if failed or type(value) is not int or not 0 <= value <= _MAX_CLOCK_NS:
            return None
        return value

    def _prune(self, now_ns: int) -> None:
        expired: list[str] = []
        for key, entry in tuple(self._entries.items()):
            if type(entry) is not _Terminal:
                continue
            if entry.retention_anchor_pending:
                self._entries[key] = _Terminal(
                    digest=entry.digest,
                    result_bytes=entry.result_bytes,
                    completed_at_ns=now_ns,
                    retention_anchor_pending=False,
                )
                continue
            if (
                entry.completed_at_ns is not None
                and now_ns >= entry.completed_at_ns
                and now_ns - entry.completed_at_ns >= _RETENTION_NS
            ):
                expired.append(key)
        for key in expired:
            del self._entries[key]

    @staticmethod
    def _decode_or_fallback(
        terminal_bytes: bytes | None,
        fallback_bytes: bytes,
        result_codec: NodeControlResultCodec,
        request_id: str,
    ) -> _ApplyResult:
        if terminal_bytes is not None:
            try:
                return _decode_terminal(terminal_bytes, result_codec, request_id)
            except Exception:
                pass
        failed = False
        decoded: _ApplyResult | None = None
        try:
            decoded = _decode_terminal(fallback_bytes, result_codec, request_id)
        except Exception:
            failed = True
        if failed or decoded is None:
            raise _NodeControlReplayContractError()
        return decoded
