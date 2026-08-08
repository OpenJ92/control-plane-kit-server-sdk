"""Closed Ed25519 admission for signed workload node-control requests."""

from __future__ import annotations

import base64
import json
import re
from typing import Callable

import jwt

from control_plane_kit_core import (
    DelegatedWorkloadNodeControlGrant,
    DelegatedWorkloadNodeControlGrantCodec,
    DelegationKeyAlgorithm,
    DelegationKeyPurpose,
    NodeControlCommandRequest,
    NodeControlCommandRequestCodec,
    NodeControlGraphReference,
    NodeControlGraphReferenceRole,
    NodeControlOperation,
    verify_workload_node_control_grant,
)
from control_plane_kit_server_sdk.verifier_keys import (
    AtomicWorkloadNodeControlVerifierKeySet,
)


_TOKEN_TYPE = "CPK-WORKLOAD-NODE-CONTROL+JWT"
_ERROR_MESSAGE = "workload node-control credential was rejected"
_MAX_CREDENTIAL_BYTES = 12_288
_MAX_HEADER_SEGMENT_BYTES = 1_024
_MAX_PAYLOAD_SEGMENT_BYTES = 8_192
_MAX_SIGNATURE_SEGMENT_BYTES = 1_024
_MAX_CANDIDATE_BYTES = 16_384
_MAX_STRUCTURAL_JSON_DEPTH = 16
_MAX_STRUCTURAL_JSON_MEMBERS = 64
_MAX_SAFE_INTEGER = 2**53 - 1
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_BASE64URL = re.compile(rb"^[A-Za-z0-9_-]+$")

_HEADER_KEYS = frozenset({"alg", "kid", "typ"})
_PAYLOAD_KEYS = frozenset(
    {"iss", "aud", "iat", "nbf", "exp", "jti", "workload_node_control"}
)
_GRANT_KEYS = frozenset(
    {
        "issuer",
        "key_id",
        "audience",
        "target",
        "variable_name",
        "operation",
        "command_codec",
        "request_id",
        "idempotency_key",
        "request_digest",
        "issued_at",
        "not_before",
        "expires_at",
        "jti",
    }
)
_TARGET_KEYS = frozenset(
    {"workspace_id", "graph_revision", "node_id", "provider_socket_name"}
)
_GRANT_TEXT_KEYS = frozenset(
    {
        "issuer",
        "key_id",
        "audience",
        "variable_name",
        "operation",
        "request_id",
        "idempotency_key",
        "request_digest",
        "jti",
    }
)


class WorkloadNodeControlVerificationError(ValueError):
    """Bounded rejection for every credential-admission failure."""

    __slots__ = ()


class _ObjectPairs(list[tuple[str, object]]):
    pass


class Ed25519WorkloadNodeControlVerifier:
    """Admit one signed end-to-end workload request with one key snapshot."""

    __slots__ = ("_holder", "_expected_issuer", "_expected_audience", "_clock")

    def __init__(
        self,
        holder: AtomicWorkloadNodeControlVerifierKeySet,
        *,
        expected_issuer: str,
        expected_audience: str,
        clock: Callable[[], int],
    ) -> None:
        if type(holder) is not AtomicWorkloadNodeControlVerifierKeySet:
            raise TypeError("workload verifier holder is invalid")
        _require_reference(expected_issuer)
        _require_reference(expected_audience)
        if not callable(clock):
            raise TypeError("workload verifier clock is invalid")
        self._holder = holder
        self._expected_issuer = expected_issuer
        self._expected_audience = expected_audience
        self._clock = clock

    def __repr__(self) -> str:
        return "Ed25519WorkloadNodeControlVerifier()"

    def admit(
        self,
        credential: bytes,
        *,
        route_operation: NodeControlOperation,
        route_variable: NodeControlGraphReference,
        candidate: bytes | None,
    ) -> NodeControlCommandRequest:
        try:
            return self._admit(
                credential,
                route_operation=route_operation,
                route_variable=route_variable,
                candidate=candidate,
            )
        except Exception:
            pass
        raise WorkloadNodeControlVerificationError(_ERROR_MESSAGE)

    def _admit(
        self,
        credential: bytes,
        *,
        route_operation: NodeControlOperation,
        route_variable: NodeControlGraphReference,
        candidate: bytes | None,
    ) -> NodeControlCommandRequest:
        if type(route_operation) is not NodeControlOperation:
            raise TypeError
        if (
            type(route_variable) is not NodeControlGraphReference
            or route_variable.role is not NodeControlGraphReferenceRole.VARIABLE
            or type(route_variable.value) is not str
        ):
            raise TypeError

        header_bytes, payload_bytes, _signature_bytes = _decode_compact(credential)
        header = _decode_structural_json(header_bytes)
        payload = _decode_structural_json(payload_bytes)
        _require_header_profile(header)
        _require_payload_profile(payload)
        key_id = header["kid"]

        snapshot = self._holder.snapshot()
        if (
            type(snapshot.purpose) is not DelegationKeyPurpose
            or snapshot.purpose is not DelegationKeyPurpose.WORKLOAD_NODE_CONTROL
        ):
            raise ValueError
        selected = tuple(key for key in snapshot.public_keys if key.key_id == key_id)
        if len(selected) != 1:
            raise ValueError
        public_key = selected[0]
        if public_key.algorithm is not DelegationKeyAlgorithm.ED25519:
            raise ValueError

        del header, payload, header_bytes, payload_bytes
        claims = jwt.decode(
            credential,
            public_key.public_key_pem,
            algorithms=["EdDSA"],
            issuer=self._expected_issuer,
            audience=self._expected_audience,
            options={
                "require": ["iss", "aud", "iat", "nbf", "exp", "jti"],
                "verify_exp": False,
                "verify_nbf": False,
                "verify_iat": False,
                "strict_aud": True,
            },
        )
        claims = _walk_structural_json(claims)
        _require_payload_profile(claims)
        grant_descriptor = claims["workload_node_control"]
        grant = DelegatedWorkloadNodeControlGrantCodec().decode(grant_descriptor)
        _require_outer_grant_congruence(claims, key_id, grant)

        now = self._clock()
        if type(now) is not int or not 0 <= now <= _MAX_SAFE_INTEGER:
            raise ValueError
        if now < grant.not_before or now >= grant.expires_at:
            raise ValueError

        if grant.operation is not route_operation:
            raise ValueError
        if grant.variable_name.value != route_variable.value:
            raise ValueError

        if grant.operation is NodeControlOperation.READ_STATE:
            if candidate is not None:
                raise TypeError
            request = NodeControlCommandRequest(
                target=grant.target,
                variable_name=grant.variable_name,
                operation=grant.operation,
                request_id=grant.request_id,
                idempotency_key=grant.idempotency_key,
            )
        else:
            if type(candidate) is not bytes or not 1 <= len(candidate) <= _MAX_CANDIDATE_BYTES:
                raise TypeError
            descriptor = _decode_structural_json(candidate)
            request = NodeControlCommandRequestCodec().decode(descriptor)

        result = verify_workload_node_control_grant(
            grant,
            request,
            expected_issuer=self._expected_issuer,
            expected_audience=self._expected_audience,
            now=now,
        )
        if not result.is_accepted:
            raise ValueError
        return request


def _require_reference(value: object) -> None:
    if type(value) is not str or not _REFERENCE.fullmatch(value):
        raise ValueError("workload verifier reference is invalid")


def _decode_compact(credential: object) -> tuple[bytes, bytes, bytes]:
    if type(credential) is not bytes or not 1 <= len(credential) <= _MAX_CREDENTIAL_BYTES:
        raise TypeError
    credential.decode("ascii")
    segments = credential.split(b".")
    if len(segments) != 3:
        raise ValueError
    bounds = (
        _MAX_HEADER_SEGMENT_BYTES,
        _MAX_PAYLOAD_SEGMENT_BYTES,
        _MAX_SIGNATURE_SEGMENT_BYTES,
    )
    decoded: list[bytes] = []
    for segment, maximum in zip(segments, bounds, strict=True):
        if not 1 <= len(segment) <= maximum or _BASE64URL.fullmatch(segment) is None:
            raise ValueError
        value = base64.b64decode(
            segment + b"=" * (-len(segment) % 4),
            altchars=b"-_",
            validate=True,
        )
        if base64.urlsafe_b64encode(value).rstrip(b"=") != segment:
            raise ValueError
        decoded.append(value)
    return decoded[0], decoded[1], decoded[2]


def _decode_structural_json(value: bytes) -> object:
    if type(value) is not bytes:
        raise TypeError
    decoded = json.loads(
        value.decode("utf-8"),
        object_pairs_hook=_ObjectPairs,
        parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
    )
    return _walk_structural_json(decoded)


def _walk_structural_json(value: object) -> object:
    member_count = [0]

    def walk(candidate: object, depth: int) -> object:
        if depth > _MAX_STRUCTURAL_JSON_DEPTH:
            raise ValueError
        if type(candidate) is _ObjectPairs:
            member_count[0] += len(candidate)
            if member_count[0] > _MAX_STRUCTURAL_JSON_MEMBERS:
                raise ValueError
            keys = [key for key, _value in candidate]
            if any(type(key) is not str for key in keys) or len(set(keys)) != len(keys):
                raise ValueError
            return {
                key: walk(nested, depth + 1)
                for key, nested in candidate
            }
        if type(candidate) is dict:
            member_count[0] += len(candidate)
            if member_count[0] > _MAX_STRUCTURAL_JSON_MEMBERS:
                raise ValueError
            if any(type(key) is not str for key in candidate):
                raise ValueError
            return {
                key: walk(nested, depth + 1)
                for key, nested in candidate.items()
            }
        if type(candidate) is list:
            return [walk(nested, depth + 1) for nested in candidate]
        if candidate is None or type(candidate) in (str, int, float, bool):
            return candidate
        raise ValueError

    return walk(value, 0)


def _require_header_profile(value: object) -> None:
    if type(value) is not dict or frozenset(value) != _HEADER_KEYS:
        raise ValueError
    if any(type(value[key]) is not str for key in _HEADER_KEYS):
        raise TypeError
    if value["alg"] != "EdDSA" or value["typ"] != _TOKEN_TYPE:
        raise ValueError


def _require_payload_profile(value: object) -> None:
    if type(value) is not dict or frozenset(value) != _PAYLOAD_KEYS:
        raise ValueError
    if any(type(value[key]) is not str for key in ("iss", "aud", "jti")):
        raise TypeError
    if any(type(value[key]) is not int for key in ("iat", "nbf", "exp")):
        raise TypeError
    grant = value["workload_node_control"]
    if type(grant) is not dict or frozenset(grant) != _GRANT_KEYS:
        raise ValueError
    if any(type(grant[key]) is not str for key in _GRANT_TEXT_KEYS):
        raise TypeError
    if grant["command_codec"] is not None and type(grant["command_codec"]) is not str:
        raise TypeError
    if any(type(grant[key]) is not int for key in ("issued_at", "not_before", "expires_at")):
        raise TypeError
    target = grant["target"]
    if type(target) is not dict or frozenset(target) != _TARGET_KEYS:
        raise ValueError
    if any(type(target[key]) is not str for key in _TARGET_KEYS):
        raise TypeError


def _require_outer_grant_congruence(
    claims: dict[str, object],
    header_key_id: str,
    grant: DelegatedWorkloadNodeControlGrant,
) -> None:
    if (
        type(header_key_id) is not str
        or header_key_id != grant.key_id
        or claims["iss"] != grant.issuer
        or claims["aud"] != grant.audience
        or claims["iat"] != grant.issued_at
        or claims["nbf"] != grant.not_before
        or claims["exp"] != grant.expires_at
        or claims["jti"] != grant.jti
    ):
        raise ValueError


__all__ = [
    "Ed25519WorkloadNodeControlVerifier",
    "WorkloadNodeControlVerificationError",
]
