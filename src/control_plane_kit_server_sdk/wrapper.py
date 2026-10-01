"""Optional verification setup and observed host lifecycle; no framework imports."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import stat
from threading import Lock
import time
from types import CoroutineType
from typing import Callable

from control_plane_kit_core import DelegationKeyPurpose, NodeHealthReadKind, NodeHealthReadOutcome, receiver_node_control_audience
from control_plane_kit_core.wrapper_configuration import (
    MAX_WRAPPER_CONFIGURATION_BYTES, WORKLOAD_NODE_CONTROL_CONFIGURATION_ENVIRONMENT,
)
from control_plane_kit_core.receiver_configuration import (
    ReceiverNodeControlConfiguration, ReceiverNodeControlConfigurationCodec,
)
from control_plane_kit_server_sdk.health import WorkloadNodeHealthReadDispatcher, _require_sync_callback
from control_plane_kit_server_sdk import verifier_keys as keys
from control_plane_kit_server_sdk import verification


class WrapperSetupError(ValueError):
    """A fixed refusal without configuration material or exception links."""


def load_wrapper_configuration() -> ReceiverNodeControlConfiguration:
    """Snapshot the delivered absolute, regular, non-symlink 0444 file once."""
    try:
        path = os.environ[WORKLOAD_NODE_CONTROL_CONFIGURATION_ENVIRONMENT]
        if not os.path.isabs(path):
            raise ValueError
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        try:
            before = os.fstat(descriptor)
            if (not stat.S_ISREG(before.st_mode) or stat.S_IMODE(before.st_mode) != 0o444
                    or before.st_size > MAX_WRAPPER_CONFIGURATION_BYTES):
                raise ValueError
            chunks = []
            remaining = MAX_WRAPPER_CONFIGURATION_BYTES + 1
            while remaining:
                chunk = os.read(descriptor, remaining)
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            after = os.fstat(descriptor)
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ValueError
            return ReceiverNodeControlConfigurationCodec().decode_bytes(b"".join(chunks))
        finally:
            os.close(descriptor)
    except Exception:
        pass
    raise WrapperSetupError("wrapper setup is invalid")


class _HostLifecycle:
    """One host's serialized phase; application callbacks run outside the lock."""
    def __init__(self, readiness):
        self._lock = Lock()
        self._phase = "stopped"
        self._epoch = 0
        self._readiness = readiness

    def begin(self) -> int:
        with self._lock:
            if self._phase != "stopped":
                raise RuntimeError("wrapper host is already active")
            self._epoch += 1
            self._phase = "starting"
            return self._epoch

    def observe(self) -> tuple[int, bool]:
        with self._lock:
            return self._epoch, self._phase == "serving"

    def serving(self, epoch: int) -> None:
        with self._lock:
            if self._epoch == epoch and self._phase == "starting":
                self._phase = "serving"

    def stop(self) -> None:
        with self._lock:
            if self._phase in ("starting", "serving"):
                self._phase = "stopping"

    def finish(self, epoch: int) -> None:
        with self._lock:
            if self._epoch == epoch:
                self._phase = "stopped"

    def readiness(self) -> NodeHealthReadOutcome:
        epoch, serving = self.observe()
        if not serving:
            return NodeHealthReadOutcome.UNHEALTHY
        outcome = NodeHealthReadOutcome.HEALTHY if self._readiness is None else self._readiness()
        if type(outcome) is not NodeHealthReadOutcome:
            if type(outcome) is CoroutineType:
                outcome.close()
            raise ValueError
        # A slow callback cannot outlive stop, or a later host invocation.
        return outcome if self.observe() == (epoch, True) else NodeHealthReadOutcome.UNHEALTHY


def _responsive() -> NodeHealthReadOutcome:
    return NodeHealthReadOutcome.HEALTHY


def _clock() -> int:
    return int(time.time())


@dataclass(frozen=True, repr=False)
class _Wrapper:
    lifecycle: _HostLifecycle
    settings: dict = field(repr=False)


def _prepare_wrapper(*, configuration: ReceiverNodeControlConfiguration | None = None,
                     clock: Callable[[], int] | None = None, liveness=None, readiness=None) -> _Wrapper:
    try:
        codec = ReceiverNodeControlConfigurationCodec()
        configuration = load_wrapper_configuration() if configuration is None else codec.decode_bytes(codec.encode_bytes(configuration))
        clock = _clock if clock is None else clock
        _require_sync_callback(clock)
        kinds = configuration.declaration.surface.health_reads
        for kind, callback in ((NodeHealthReadKind.LIVENESS, liveness), (NodeHealthReadKind.READINESS, readiness)):
            if callback is not None:
                if kind not in kinds:
                    raise ValueError
                _require_sync_callback(callback)
        lifecycle = _HostLifecycle(readiness)
        factories = {
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL: (
                keys.WorkloadNodeControlVerifierKeySet, keys.AtomicWorkloadNodeControlVerifierKeySet,
                verification.Ed25519WorkloadNodeControlVerifier),
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ: (
                keys.WorkloadNodeControlSurfaceReadVerifierKeySet, keys.AtomicWorkloadNodeControlSurfaceReadVerifierKeySet,
                verification.Ed25519WorkloadNodeControlSurfaceReadVerifier),
            DelegationKeyPurpose.WORKLOAD_NODE_HEALTH_READ: (
                keys.WorkloadNodeHealthReadVerifierKeySet, keys.AtomicWorkloadNodeHealthReadVerifierKeySet,
                verification.Ed25519WorkloadNodeHealthReadVerifier),
        }
        verifiers = {}
        for family in configuration.verifiers:
            snapshot, holder, verifier = factories[family.purpose]
            verifiers[family.purpose] = verifier(holder(snapshot(family.purpose, family.public_keys)),
                expected_issuer=family.issuer, expected_audience=receiver_node_control_audience(configuration.target), clock=clock)
        dispatcher = None
        if kinds:
            dispatcher = WorkloadNodeHealthReadDispatcher(
                target=configuration.target, declaration=configuration.declaration,
                verifier=verifiers[DelegationKeyPurpose.WORKLOAD_NODE_HEALTH_READ],
                liveness=(_responsive if liveness is None else liveness) if NodeHealthReadKind.LIVENESS in kinds else None,
                readiness=lifecycle.readiness if NodeHealthReadKind.READINESS in kinds else None,
            )
        return _Wrapper(lifecycle, dict(target=configuration.target, declaration=configuration.declaration,
            command_verifier=verifiers.get(DelegationKeyPurpose.WORKLOAD_NODE_CONTROL),
            surface_read_verifier=verifiers[DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ], health_dispatcher=dispatcher))
    except Exception:
        pass
    raise WrapperSetupError("wrapper setup is invalid")


__all__ = ["WrapperSetupError", "load_wrapper_configuration"]
