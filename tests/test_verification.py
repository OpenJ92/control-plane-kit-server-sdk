from __future__ import annotations

import ast
import base64
from contextlib import contextmanager
from dataclasses import dataclass, replace
import importlib
import json
from pathlib import Path
from threading import Event, Thread
import unittest

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

from control_plane_kit_core import (
    ControlPlaneCommandCodec,
    ControlPlaneTransitionPrecondition,
    DelegatedWorkloadNodeControlGrant,
    DelegatedWorkloadNodeControlSurfaceReadGrant,
    DelegatedWorkloadNodeControlSurfaceReadGrantCodec,
    DelegatedWorkloadNodeControlSurfaceReadGrantProfile,
    DelegationKeyAlgorithm,
    DelegationKeyPurpose,
    DelegationPublicKey,
    NodeControlCanonicalization,
    NodeControlCommandRequest,
    NodeControlCommandRequestCodec,
    NodeControlGraphReference,
    NodeControlGraphReferenceRole,
    NodeControlOperation,
    NodeControlPayload,
    NodeControlRequestDigest,
    NodeControlSurfaceReadKind,
    NodeControlSurfaceReadRequest,
    NodeControlSurfaceReadRequestDigest,
    NodeControlTarget,
    ScalarControlState,
    WorkloadNodeControlSurfaceDeclarationIdentity,
)
from control_plane_kit_server_sdk.verifier_keys import (
    AtomicWorkloadNodeControlVerifierKeySet,
    WorkloadNodeControlVerifierKeySet,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "control_plane_kit_server_sdk"
VERIFICATION_MODULE = "control_plane_kit_server_sdk.verification"
TOKEN_TYPE = "CPK-WORKLOAD-NODE-CONTROL+JWT"
ERROR_MESSAGE = "workload node-control credential was rejected"
ISSUER = "cpk-server"
AUDIENCE = "workload:router:control"
NOW = 150
BASE64URL_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
MAX_STRUCTURAL_JSON_DEPTH = 16
MAX_STRUCTURAL_JSON_MEMBERS = 64
SURFACE_TOKEN_TYPE = "CPK-WORKLOAD-NODE-CONTROL-SURFACE-READ+JWT"
SURFACE_PAYLOAD_KEY = "workload_node_control_surface_read"
SURFACE_ERROR_MESSAGE = "workload node-control surface-read credential was rejected"
MAX_SURFACE_CREDENTIAL_BYTES = 4_096
MAX_SURFACE_HEADER_SEGMENT_BYTES = 512
MAX_SURFACE_PAYLOAD_SEGMENT_BYTES = 3_840
MAX_SURFACE_SIGNATURE_SEGMENT_BYTES = 128
_UNSET = object()


@dataclass(frozen=True)
class RawJson:
    data: bytes


class SensitiveCandidate:
    def __repr__(self) -> str:
        return "authorization: Bearer candidate-secret"


class ExplodingReprCandidate:
    def __repr__(self) -> str:
        raise AssertionError("candidate repr must not be evaluated")


class SensitiveText(str):
    def __repr__(self) -> str:
        return "authorization: Bearer nested-secret"

    def __eq__(self, _other: object) -> bool:
        raise AssertionError("nested equality must not run")

    def __hash__(self) -> int:
        raise AssertionError("nested hashing must not run")


def _json_value(value: object) -> bytes:
    if isinstance(value, RawJson):
        return value.data
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _raw_object(pairs: list[tuple[str, object]]) -> bytes:
    return b"{" + b",".join(
        json.dumps(key).encode("ascii") + b":" + _json_value(value)
        for key, value in pairs
    ) + b"}"


def _duplicate_pair(
    mapping: dict[str, object],
    key: str,
    *,
    value: object | None = None,
) -> list[tuple[str, object]]:
    pairs: list[tuple[str, object]] = []
    for candidate_key, candidate_value in mapping.items():
        pairs.append((candidate_key, candidate_value))
        if candidate_key == key:
            pairs.append((candidate_key, candidate_value if value is None else value))
    return pairs


def _b64url(value: bytes) -> bytes:
    return base64.urlsafe_b64encode(value).rstrip(b"=")


def _b64url_decode(value: bytes) -> bytes:
    return base64.urlsafe_b64decode(value + b"=" * (-len(value) % 4))


def _noncanonical_tail(segment: bytes) -> bytes:
    index = BASE64URL_ALPHABET.index(chr(segment[-1]))
    significant_bits = {2: 2, 3: 4}.get(len(segment) % 4)
    if significant_bits is None:
        raise AssertionError("fixture segment has no base64url pad bits")
    pad_bits = 6 - significant_bits
    candidates = (
        candidate
        for candidate in range(64)
        if candidate != index and candidate >> pad_bits == index >> pad_bits
    )
    replacement = BASE64URL_ALPHABET[next(candidates)].encode("ascii")
    mutated = segment[:-1] + replacement
    if _b64url_decode(mutated) != _b64url_decode(segment):
        raise AssertionError("fixture did not preserve decoded signature bytes")
    return mutated


def _json_with_pad_bits(value: dict[str, object]) -> bytes:
    encoded = _json_value(value)
    while len(encoded) % 3 == 0:
        encoded += b" "
    return encoded


def _public_pem(private_key: ed25519.Ed25519PrivateKey) -> str:
    return private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def _reference(
    role: NodeControlGraphReferenceRole,
    value: str,
) -> NodeControlGraphReference:
    return NodeControlGraphReference(role, value)


def _target(**changes: object) -> NodeControlTarget:
    values: dict[str, object] = {
        "workspace_id": _reference(NodeControlGraphReferenceRole.WORKSPACE, "workspace-1"),
        "graph_revision": _reference(
            NodeControlGraphReferenceRole.GRAPH_REVISION,
            "revision-7",
        ),
        "node_id": _reference(NodeControlGraphReferenceRole.NODE, "router"),
        "provider_socket_name": _reference(
            NodeControlGraphReferenceRole.PROVIDER_SOCKET,
            "control",
        ),
    }
    values.update(changes)
    return NodeControlTarget(**values)


def _variable(value: str = "routing") -> NodeControlGraphReference:
    return _reference(NodeControlGraphReferenceRole.VARIABLE, value)


def _request(
    operation: NodeControlOperation = NodeControlOperation.APPLY_COMMAND,
    **changes: object,
) -> NodeControlCommandRequest:
    values: dict[str, object] = {
        "target": _target(),
        "variable_name": _variable(),
        "operation": operation,
        "request_id": "request-1",
        "idempotency_key": "routing-change-1",
    }
    if operation is NodeControlOperation.APPLY_COMMAND:
        values.update(
            command_codec=ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
            precondition=ControlPlaneTransitionPrecondition(expected_version=4),
            payload=NodeControlPayload(
                codec=ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
                state=ScalarControlState("green"),
            ),
        )
    values.update(changes)
    return NodeControlCommandRequest(**values)


def _grant(
    request: NodeControlCommandRequest,
    *,
    key_id: str = "workload-key-a",
    **changes: object,
) -> DelegatedWorkloadNodeControlGrant:
    values: dict[str, object] = {
        "issuer": ISSUER,
        "key_id": key_id,
        "audience": AUDIENCE,
        "target": request.target,
        "variable_name": request.variable_name,
        "operation": request.operation,
        "command_codec": request.command_codec,
        "request_id": request.request_id,
        "idempotency_key": request.idempotency_key,
        "request_digest": request.canonical_digest(),
        "issued_at": 100,
        "not_before": 100,
        "expires_at": 200,
        "jti": "grant-1",
    }
    values.update(changes)
    return DelegatedWorkloadNodeControlGrant(**values)


def _payload(grant_value: object, **changes: object) -> dict[str, object]:
    if isinstance(grant_value, DelegatedWorkloadNodeControlGrant):
        grant_descriptor: object = grant_value.descriptor()
        values: dict[str, object] = {
            "iss": grant_value.issuer,
            "aud": grant_value.audience,
            "iat": grant_value.issued_at,
            "nbf": grant_value.not_before,
            "exp": grant_value.expires_at,
            "jti": grant_value.jti,
            "workload_node_control": grant_descriptor,
        }
    else:
        values = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": 100,
            "nbf": 100,
            "exp": 200,
            "jti": "grant-1",
            "workload_node_control": grant_value,
        }
    values.update(changes)
    return values


def _header(key_id: str = "workload-key-a", **changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "alg": "EdDSA",
        "kid": key_id,
        "typ": TOKEN_TYPE,
    }
    values.update(changes)
    return values


def _signed_compact(
    private_key: ed25519.Ed25519PrivateKey,
    *,
    header_bytes: bytes,
    payload_bytes: bytes,
    signature_segment: bytes | None = None,
) -> bytes:
    header_segment = _b64url(header_bytes)
    payload_segment = _b64url(payload_bytes)
    signing_input = header_segment + b"." + payload_segment
    signature = _b64url(private_key.sign(signing_input))
    return signing_input + b"." + (
        signature if signature_segment is None else signature_segment
    )


def _token(
    private_key: ed25519.Ed25519PrivateKey,
    grant: DelegatedWorkloadNodeControlGrant,
    *,
    header_changes: dict[str, object] | None = None,
    payload_changes: dict[str, object] | None = None,
) -> bytes:
    header = _header(grant.key_id, **(header_changes or {}))
    payload = _payload(grant, **(payload_changes or {}))
    return _signed_compact(
        private_key,
        header_bytes=_json_value(header),
        payload_bytes=_json_value(payload),
    )


def _candidate(request: NodeControlCommandRequest) -> bytes:
    return _json_value(request.descriptor())


def _surface_request(
    kind: NodeControlSurfaceReadKind = NodeControlSurfaceReadKind.CAPABILITIES,
    **changes: object,
) -> NodeControlSurfaceReadRequest:
    values: dict[str, object] = {
        "target": _target(),
        "kind": kind,
        "declaration_identity": WorkloadNodeControlSurfaceDeclarationIdentity(
            "d" * 64
        ),
        "request_id": "surface-read-1",
    }
    values.update(changes)
    return NodeControlSurfaceReadRequest(**values)


def _surface_grant(
    request: NodeControlSurfaceReadRequest,
    *,
    key_id: str = "surface-key-a",
    **changes: object,
) -> DelegatedWorkloadNodeControlSurfaceReadGrant:
    values: dict[str, object] = {
        "profile": DelegatedWorkloadNodeControlSurfaceReadGrantProfile.V1,
        "canonicalization": NodeControlCanonicalization.JCS_RFC8785_V1,
        "purpose": DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
        "issuer": ISSUER,
        "key_id": key_id,
        "audience": AUDIENCE,
        "target": request.target,
        "kind": request.kind,
        "declaration_identity": request.declaration_identity,
        "request_id": request.request_id,
        "request_digest": request.canonical_digest(),
        "issued_at": 100,
        "not_before": 100,
        "expires_at": 200,
        "jti": "surface-grant-1",
    }
    values.update(changes)
    return DelegatedWorkloadNodeControlSurfaceReadGrant(**values)


def _surface_payload(
    grant_value: object,
    **changes: object,
) -> dict[str, object]:
    if isinstance(grant_value, DelegatedWorkloadNodeControlSurfaceReadGrant):
        values: dict[str, object] = {
            "iss": grant_value.issuer,
            "aud": grant_value.audience,
            "iat": grant_value.issued_at,
            "nbf": grant_value.not_before,
            "exp": grant_value.expires_at,
            "jti": grant_value.jti,
            SURFACE_PAYLOAD_KEY: grant_value.descriptor(),
        }
    else:
        values = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": 100,
            "nbf": 100,
            "exp": 200,
            "jti": "surface-grant-1",
            SURFACE_PAYLOAD_KEY: grant_value,
        }
    values.update(changes)
    return values


def _surface_header(
    key_id: str = "surface-key-a",
    **changes: object,
) -> dict[str, object]:
    values: dict[str, object] = {
        "alg": "EdDSA",
        "kid": key_id,
        "typ": SURFACE_TOKEN_TYPE,
    }
    values.update(changes)
    return values


def _surface_token(
    private_key: ed25519.Ed25519PrivateKey,
    grant: DelegatedWorkloadNodeControlSurfaceReadGrant,
    *,
    header_changes: dict[str, object] | None = None,
    payload_changes: dict[str, object] | None = None,
) -> bytes:
    return _signed_compact(
        private_key,
        header_bytes=_json_value(
            _surface_header(grant.key_id, **(header_changes or {}))
        ),
        payload_bytes=_json_value(
            _surface_payload(grant, **(payload_changes or {}))
        ),
    )


@contextmanager
def _replaced_attribute(owner: object, name: str, replacement: object):
    original = getattr(owner, name)
    setattr(owner, name, replacement)
    try:
        yield
    finally:
        setattr(owner, name, original)


class SignedWorkloadVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_a = ed25519.Ed25519PrivateKey.generate()
        self.private_b = ed25519.Ed25519PrivateKey.generate()
        self.key_a = DelegationPublicKey(
            "workload-key-a",
            DelegationKeyAlgorithm.ED25519,
            _public_pem(self.private_a),
        )
        self.key_b = DelegationPublicKey(
            "workload-key-b",
            DelegationKeyAlgorithm.ED25519,
            _public_pem(self.private_b),
        )
        self.snapshot_a = self._snapshot(self.key_a)
        self.snapshot_a_b = self._snapshot(self.key_b, self.key_a)
        self.snapshot_b = self._snapshot(self.key_b)
        self.holder = AtomicWorkloadNodeControlVerifierKeySet(self.snapshot_a)

    def _module(self):
        try:
            return importlib.import_module(VERIFICATION_MODULE)
        except ModuleNotFoundError:
            self.fail("signed workload verification module is not implemented")

    def _snapshot(
        self,
        *keys: DelegationPublicKey,
    ) -> WorkloadNodeControlVerifierKeySet:
        return WorkloadNodeControlVerifierKeySet(
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
            keys,
        )

    def _verifier(self, *, holder=None, clock=None, issuer=ISSUER, audience=AUDIENCE):
        module = self._module()
        return module.Ed25519WorkloadNodeControlVerifier(
            self.holder if holder is None else holder,
            expected_issuer=issuer,
            expected_audience=audience,
            clock=(lambda: NOW) if clock is None else clock,
        )

    def _admit(
        self,
        token: bytes,
        request: NodeControlCommandRequest,
        *,
        verifier=None,
        route_operation: NodeControlOperation | None = None,
        route_variable: NodeControlGraphReference | None = None,
        candidate: object = ...,
    ) -> NodeControlCommandRequest:
        selected_candidate = (
            (None if request.operation is NodeControlOperation.READ_STATE else _candidate(request))
            if candidate is ...
            else candidate
        )
        return (verifier or self._verifier()).admit(
            token,
            route_operation=request.operation if route_operation is None else route_operation,
            route_variable=request.variable_name if route_variable is None else route_variable,
            candidate=selected_candidate,
        )

    def _assert_rejected(self, operation) -> BaseException:
        module = self._module()
        with self.assertRaises(module.WorkloadNodeControlVerificationError) as raised:
            operation()
        self.assertEqual(str(raised.exception), ERROR_MESSAGE)
        self.assertEqual(
            repr(raised.exception),
            f"WorkloadNodeControlVerificationError({ERROR_MESSAGE!r})",
        )
        self.assertEqual(vars(raised.exception), {})
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        return raised.exception

    def _assert_pre_auth_rejected(
        self,
        token: bytes,
        *,
        candidate: object = b"{malformed-candidate",
    ) -> None:
        request = _request()
        jwt_calls = 0
        candidate_calls = 0

        def forbidden_jwt(*_args: object, **_kwargs: object) -> object:
            nonlocal jwt_calls
            jwt_calls += 1
            raise AssertionError("maintained signature admission was reached")

        def forbidden_candidate(*_args: object, **_kwargs: object) -> object:
            nonlocal candidate_calls
            candidate_calls += 1
            raise AssertionError("candidate decoder was reached")

        with _replaced_attribute(jwt, "decode", forbidden_jwt), _replaced_attribute(
            NodeControlCommandRequestCodec,
            "decode",
            forbidden_candidate,
        ):
            self._assert_rejected(
                lambda: self._admit(token, request, candidate=candidate)
            )
        self.assertEqual(jwt_calls, 0)
        self.assertEqual(candidate_calls, 0)

    def test_test_owned_ed25519_fixture_is_accepted_by_maintained_pyjwt(self) -> None:
        request = _request()
        grant = _grant(request)
        token = _token(self.private_a, grant)

        claims = jwt.decode(
            token,
            self.key_a.public_key_pem,
            algorithms=["EdDSA"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"verify_exp": False, "verify_nbf": False, "verify_iat": False},
        )

        self.assertEqual(claims, _payload(grant))

    def test_noncanonical_signature_fixture_preserves_exact_decoded_bytes(self) -> None:
        request = _request()
        token = _token(self.private_a, _grant(request))
        header, payload, signature = token.split(b".")
        mutated_signature = _noncanonical_tail(signature)

        self.assertNotEqual(mutated_signature, signature)
        self.assertEqual(
            _b64url_decode(mutated_signature),
            _b64url_decode(signature),
        )
        self.assertNotEqual(b".".join((header, payload, mutated_signature)), token)

    def test_public_module_exports_only_one_verifier_and_one_error(self) -> None:
        module = self._module()

        self.assertEqual(
            module.__all__,
            [
                "Ed25519WorkloadNodeControlVerifier",
                "WorkloadNodeControlVerificationError",
            ],
        )
        self.assertEqual(module.Ed25519WorkloadNodeControlVerifier.__module__, VERIFICATION_MODULE)
        self.assertEqual(module.WorkloadNodeControlVerificationError.__module__, VERIFICATION_MODULE)
        root = importlib.import_module("control_plane_kit_server_sdk")
        self.assertNotIn("Ed25519WorkloadNodeControlVerifier", root.__all__)
        self.assertFalse(hasattr(root, "Ed25519WorkloadNodeControlVerifier"))

    def test_constructor_is_exact_bounded_slotted_and_redacted(self) -> None:
        verifier = self._verifier()

        self.assertEqual(repr(verifier), "Ed25519WorkloadNodeControlVerifier()")
        self.assertFalse(hasattr(verifier, "__dict__"))
        for value, keyword in (
            (object(), "holder"),
            (SensitiveText(ISSUER), "issuer"),
            (SensitiveText(AUDIENCE), "audience"),
            (object(), "clock"),
        ):
            with self.subTest(keyword=keyword):
                arguments = {
                    "holder": self.holder,
                    "issuer": ISSUER,
                    "audience": AUDIENCE,
                    "clock": lambda: NOW,
                }
                arguments[keyword] = value
                with self.assertRaises((TypeError, ValueError)) as raised:
                    self._verifier(
                        holder=arguments["holder"],
                        issuer=arguments["issuer"],
                        audience=arguments["audience"],
                        clock=arguments["clock"],
                    )
                self.assertNotIn("nested-secret", str(raised.exception))

    def test_read_and_apply_return_exact_nominal_requests(self) -> None:
        for request in (
            _request(NodeControlOperation.READ_STATE),
            _request(NodeControlOperation.APPLY_COMMAND),
        ):
            with self.subTest(operation=request.operation):
                token = _token(self.private_a, _grant(request))
                admitted = self._admit(token, request)
                self.assertIs(type(admitted), NodeControlCommandRequest)
                self.assertEqual(admitted, request)
                self.assertEqual(
                    NodeControlCommandRequestCodec().decode(admitted.descriptor()),
                    request,
                )
                self.assertEqual(admitted.canonical_digest(), request.canonical_digest())

    def test_credential_and_candidate_outer_types_are_closed_without_repr(self) -> None:
        request = _request()
        token = _token(self.private_a, _grant(request))
        for candidate_token in ("token", bytearray(token), SensitiveCandidate(), ExplodingReprCandidate()):
            with self.subTest(token_type=type(candidate_token).__name__):
                self._assert_rejected(
                    lambda candidate_token=candidate_token: self._admit(
                        candidate_token,
                        request,
                    )
                )
        for candidate in ("{}", bytearray(b"{}"), SensitiveCandidate(), ExplodingReprCandidate()):
            with self.subTest(candidate_type=type(candidate).__name__):
                self._assert_rejected(
                    lambda candidate=candidate: self._admit(
                        token,
                        request,
                        candidate=candidate,
                    )
                )

    def test_compact_framing_ascii_and_segment_bounds_reject_before_pyjwt(self) -> None:
        cases = (
            b"",
            b"a.b",
            b"a.b.c.d",
            b".b.c",
            b"a..c",
            b"a.b.",
            b"a=.b.c",
            b"a.b.%%",
            (b"A" * 1025) + b".b.c",
            b"a." + (b"A" * 8193) + b".c",
            b"a.b." + (b"A" * 1025),
            b"A" * 12289,
            b"a.b.c\xff",
        )
        for identity, token in enumerate(cases):
            with self.subTest(identity=identity):
                self._assert_pre_auth_rejected(token)

    def test_all_three_compact_segments_require_canonical_base64url_spelling(self) -> None:
        request = _request()
        grant = _grant(request)
        header_bytes = _json_with_pad_bits(_header())
        payload_bytes = _json_with_pad_bits(_payload(grant))
        canonical = _signed_compact(
            self.private_a,
            header_bytes=header_bytes,
            payload_bytes=payload_bytes,
        )
        header, payload, signature = canonical.split(b".")
        mutated_header = _noncanonical_tail(header)
        mutated_payload = _noncanonical_tail(payload)
        # Header/payload mutations need signatures over their exact noncanonical text.
        tokens = (
            mutated_header
            + b"."
            + payload
            + b"."
            + _b64url(self.private_a.sign(mutated_header + b"." + payload)),
            header
            + b"."
            + mutated_payload
            + b"."
            + _b64url(self.private_a.sign(header + b"." + mutated_payload)),
            b".".join((header, payload, _noncanonical_tail(signature))),
        )
        for identity, token in zip(("header", "payload", "signature"), tokens, strict=True):
            with self.subTest(identity=identity):
                self._assert_pre_auth_rejected(token)

    def test_noncanonical_signature_tail_rejects_before_pyjwt(self) -> None:
        request = _request()
        token = _token(self.private_a, _grant(request))
        header, payload, signature = token.split(b".")
        mutated = b".".join((header, payload, _noncanonical_tail(signature)))

        self.assertEqual(_b64url_decode(mutated.split(b".")[2]), _b64url_decode(signature))
        self._assert_pre_auth_rejected(mutated)

    def test_duplicate_header_members_reject_before_pyjwt_and_candidate(self) -> None:
        request = _request()
        grant = _grant(request)
        payload_bytes = _json_value(_payload(grant))
        header = _header()
        for key in ("alg", "kid", "typ"):
            with self.subTest(key=key):
                token = _signed_compact(
                    self.private_a,
                    header_bytes=_raw_object(_duplicate_pair(header, key)),
                    payload_bytes=payload_bytes,
                )
                self._assert_pre_auth_rejected(token)

    def test_duplicate_payload_members_reject_before_pyjwt_and_candidate(self) -> None:
        request = _request()
        grant = _grant(request)
        payload = _payload(grant)
        for key in ("iss", "aud", "iat", "nbf", "exp", "jti", "workload_node_control"):
            with self.subTest(key=key):
                token = _signed_compact(
                    self.private_a,
                    header_bytes=_json_value(_header()),
                    payload_bytes=_raw_object(_duplicate_pair(payload, key)),
                )
                self._assert_pre_auth_rejected(token)

    def test_duplicate_grant_members_reject_before_pyjwt_and_candidate(self) -> None:
        request = _request()
        grant = _grant(request)
        grant_descriptor = grant.descriptor()
        for key in (
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
        ):
            with self.subTest(key=key):
                raw_grant = _raw_object(_duplicate_pair(grant_descriptor, key))
                raw_payload = _raw_object(
                    list(_payload(grant).items())[:-1]
                    + [("workload_node_control", RawJson(raw_grant))]
                )
                token = _signed_compact(
                    self.private_a,
                    header_bytes=_json_value(_header()),
                    payload_bytes=raw_payload,
                )
                self._assert_pre_auth_rejected(token)

    def test_duplicate_target_and_unknown_members_reject_at_every_depth(self) -> None:
        request = _request()
        grant = _grant(request)
        target_descriptor = grant.target.descriptor()
        for key in ("workspace_id", "graph_revision", "node_id", "provider_socket_name"):
            with self.subTest(target_key=key):
                raw_target = _raw_object(_duplicate_pair(target_descriptor, key))
                grant_pairs = [
                    (name, RawJson(raw_target) if name == "target" else value)
                    for name, value in grant.descriptor().items()
                ]
                raw_payload = _raw_object(
                    [
                        (name, RawJson(_raw_object(grant_pairs)) if name == "workload_node_control" else value)
                        for name, value in _payload(grant).items()
                    ]
                )
                token = _signed_compact(
                    self.private_a,
                    header_bytes=_json_value(_header()),
                    payload_bytes=raw_payload,
                )
                self._assert_pre_auth_rejected(token)

    def test_closed_profile_rejects_missing_unknown_nonobject_and_wrong_types(self) -> None:
        request = _request()
        grant = _grant(request)
        header = _header()
        payload = _payload(grant)
        grant_descriptor = grant.descriptor()
        target_descriptor = grant.target.descriptor()
        cases: list[tuple[bytes, bytes]] = [
            (_json_value({key: value for key, value in header.items() if key != "typ"}), _json_value(payload)),
            (_json_value({**header, "x": 1}), _json_value(payload)),
            (b"[]", _json_value(payload)),
            (_json_value(header), _json_value({key: value for key, value in payload.items() if key != "jti"})),
            (_json_value(header), _json_value({**payload, "x": 1})),
            (_json_value(header), b"[]"),
            (
                _json_value(header),
                _json_value(
                    {
                        **payload,
                        "workload_node_control": {
                            key: value
                            for key, value in grant_descriptor.items()
                            if key != "request_digest"
                        },
                    }
                ),
            ),
            (
                _json_value(header),
                _json_value(
                    {
                        **payload,
                        "workload_node_control": {**grant_descriptor, "x": 1},
                    }
                ),
            ),
            (
                _json_value(header),
                _json_value(
                    {
                        **payload,
                        "workload_node_control": {
                            **grant_descriptor,
                            "target": {
                                key: value
                                for key, value in target_descriptor.items()
                                if key != "node_id"
                            },
                        },
                    }
                ),
            ),
            (
                _json_value(header),
                _json_value(
                    {
                        **payload,
                        "workload_node_control": {
                            **grant_descriptor,
                            "target": {**target_descriptor, "x": 1},
                        },
                    }
                ),
            ),
            (_json_value({**header, "kid": 7}), _json_value(payload)),
            (_json_value(header), _json_value({**payload, "iss": 7})),
        ]
        for identity, (header_bytes, payload_bytes) in enumerate(cases):
            with self.subTest(identity=identity):
                token = _signed_compact(
                    self.private_a,
                    header_bytes=header_bytes,
                    payload_bytes=payload_bytes,
                )
                self._assert_pre_auth_rejected(token)

        for depth in ("header", "payload", "grant", "target"):
            with self.subTest(unknown_depth=depth):
                header_pairs = list(_header().items())
                payload_pairs = list(_payload(grant).items())
                grant_pairs = list(grant.descriptor().items())
                target_pairs = list(target_descriptor.items())
                if depth == "header":
                    header_pairs.extend((("unknown", 1), ("unknown", 1)))
                elif depth == "payload":
                    payload_pairs.extend((("unknown", 1), ("unknown", 1)))
                elif depth == "grant":
                    grant_pairs.extend((("unknown", 1), ("unknown", 1)))
                    payload_pairs[-1] = (
                        "workload_node_control",
                        RawJson(_raw_object(grant_pairs)),
                    )
                else:
                    target_pairs.extend((("unknown", 1), ("unknown", 1)))
                    grant_pairs = [
                        (name, RawJson(_raw_object(target_pairs)) if name == "target" else value)
                        for name, value in grant_pairs
                    ]
                    payload_pairs[-1] = (
                        "workload_node_control",
                        RawJson(_raw_object(grant_pairs)),
                    )
                token = _signed_compact(
                    self.private_a,
                    header_bytes=_raw_object(header_pairs),
                    payload_bytes=_raw_object(payload_pairs),
                )
                self._assert_pre_auth_rejected(token)

    def test_recursive_depth_and_member_budgets_reject_before_pyjwt(self) -> None:
        request = _request()
        grant = _grant(request)
        excessive_depth = (
            b"[" * (MAX_STRUCTURAL_JSON_DEPTH + 1)
            + b"0"
            + b"]" * (MAX_STRUCTURAL_JSON_DEPTH + 1)
        )
        excessive_members = _raw_object(
            [
                (f"member_{index:02d}", index)
                for index in range(MAX_STRUCTURAL_JSON_MEMBERS + 1)
            ]
        )
        tokens = tuple(
            _signed_compact(
                self.private_a,
                header_bytes=_json_value(_header()),
                payload_bytes=_raw_object(
                    [
                        (
                            name,
                            RawJson(candidate)
                            if name == "workload_node_control"
                            else value,
                        )
                        for name, value in _payload(grant).items()
                    ]
                ),
            )
            for candidate in (excessive_depth, excessive_members)
        )

        for identity, token in zip(("depth", "members"), tokens, strict=True):
            with self.subTest(identity=identity):
                self.assertLessEqual(len(token.split(b".")[1]), 8192)
                self._assert_pre_auth_rejected(token)

    def test_bad_signature_profile_key_and_transit_substitution_never_decode_candidate(self) -> None:
        request = _request()
        grant = _grant(request)
        malformed_candidate = b'{"request_id":"a","request_id":"b"}'
        cases = (
            _token(self.private_b, grant),
            _token(self.private_a, grant, header_changes={"alg": "HS256"}),
            _token(self.private_a, grant, header_changes={"typ": "CPK-GATEWAY-PROBE+JWT"}),
            _token(self.private_a, grant, header_changes={"kid": "unknown-key"}),
            _signed_compact(
                self.private_a,
                header_bytes=_json_value(_header()),
                payload_bytes=_json_value(
                    _payload({"gateway_probe_grant": "transit-authority"})
                ),
            ),
        )
        for identity, token in enumerate(cases):
            with self.subTest(identity=identity):
                candidate_calls = 0

                def forbidden_candidate(*_args: object, **_kwargs: object) -> object:
                    nonlocal candidate_calls
                    candidate_calls += 1
                    raise AssertionError("candidate decoder was reached")

                with _replaced_attribute(
                    NodeControlCommandRequestCodec,
                    "decode",
                    forbidden_candidate,
                ):
                    self._assert_rejected(
                        lambda token=token: self._admit(
                            token,
                            request,
                            candidate=malformed_candidate,
                        )
                    )
                self.assertEqual(candidate_calls, 0)

    def test_expired_and_not_yet_valid_grants_reject_before_candidate_with_one_clock(self) -> None:
        request = _request()
        grants = (
            _grant(request, issued_at=0, not_before=0, expires_at=NOW),
            _grant(request, issued_at=NOW + 1, not_before=NOW + 1, expires_at=NOW + 2),
        )
        for identity, grant in enumerate(grants):
            with self.subTest(identity=identity):
                clock_calls = 0
                candidate_calls = 0

                def clock() -> int:
                    nonlocal clock_calls
                    clock_calls += 1
                    return NOW

                def forbidden_candidate(*_args: object, **_kwargs: object) -> object:
                    nonlocal candidate_calls
                    candidate_calls += 1
                    raise AssertionError("candidate decoder was reached")

                with _replaced_attribute(
                    NodeControlCommandRequestCodec,
                    "decode",
                    forbidden_candidate,
                ):
                    self._assert_rejected(
                        lambda: self._admit(
                            _token(self.private_a, grant),
                            request,
                            verifier=self._verifier(clock=clock),
                            candidate=b"{hostile-malformed-candidate",
                        )
                    )
                self.assertEqual(clock_calls, 1)
                self.assertEqual(candidate_calls, 0)

    def test_valid_admission_reads_clock_exactly_once_and_reuses_now(self) -> None:
        request = _request()
        grant = _grant(request)
        clock_calls = 0

        def clock() -> int:
            nonlocal clock_calls
            clock_calls += 1
            return NOW

        admitted = self._admit(
            _token(self.private_a, grant),
            request,
            verifier=self._verifier(clock=clock),
        )
        self.assertEqual(admitted, request)
        self.assertEqual(clock_calls, 1)

    def test_apply_candidate_is_strict_only_after_valid_authentication(self) -> None:
        request = _request()
        grant = _grant(request)
        token = _token(self.private_a, grant)
        descriptor = request.descriptor()
        duplicate = _raw_object(_duplicate_pair(descriptor, "request_id"))
        unknown = _json_value({**descriptor, "body": "not-a-command"})
        cases = (b"{", b"[]", b"\xff", duplicate, unknown, b"x" * 16385)
        for identity, candidate in enumerate(cases):
            with self.subTest(identity=identity):
                self._assert_rejected(
                    lambda candidate=candidate: self._admit(
                        token,
                        request,
                        candidate=candidate,
                    )
                )

        read = _request(NodeControlOperation.READ_STATE)
        self._assert_rejected(
            lambda: self._admit(
                _token(self.private_a, _grant(read)),
                read,
                candidate=b"{}",
            )
        )

    def test_outer_claims_and_embedded_grant_must_be_exactly_congruent(self) -> None:
        request = _request()
        grant = _grant(request)
        cases = (
            {"iss": "other-issuer"},
            {"aud": "other-audience"},
            {"iat": 101},
            {"nbf": 101},
            {"exp": 199},
            {"jti": "grant-other"},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                self._assert_rejected(
                    lambda changes=changes: self._admit(
                        _token(self.private_a, grant, payload_changes=changes),
                        request,
                    )
                )

    def test_registered_claims_and_time_domain_are_strict(self) -> None:
        request = _request()
        grant = _grant(request)
        cases = (
            _token(self.private_a, grant, payload_changes={"iss": ISSUER + "-other"}),
            _token(self.private_a, grant, payload_changes={"aud": [AUDIENCE]}),
            _token(self.private_a, grant, payload_changes={"iat": 100.0}),
            _token(self.private_a, grant, payload_changes={"nbf": True}),
            _token(self.private_a, grant, payload_changes={"exp": "200"}),
            _token(self.private_a, grant, payload_changes={"jti": 1}),
        )
        for identity, token in enumerate(cases):
            with self.subTest(identity=identity):
                self._assert_rejected(lambda token=token: self._admit(token, request))

        for clock_value in (-1, True, 150.0, "150"):
            with self.subTest(clock_value=clock_value):
                self._assert_rejected(
                    lambda clock_value=clock_value: self._admit(
                        _token(self.private_a, grant),
                        request,
                        verifier=self._verifier(clock=lambda: clock_value),
                    )
                )

    def test_every_core_request_binding_and_route_binding_is_exact(self) -> None:
        request = _request()
        target_changes = (
            {"workspace_id": _reference(NodeControlGraphReferenceRole.WORKSPACE, "workspace-2")},
            {"graph_revision": _reference(NodeControlGraphReferenceRole.GRAPH_REVISION, "revision-8")},
            {"node_id": _reference(NodeControlGraphReferenceRole.NODE, "router-2")},
            {"provider_socket_name": _reference(NodeControlGraphReferenceRole.PROVIDER_SOCKET, "control-2")},
        )
        grants = [
            _grant(request, target=_target(**changes)) for changes in target_changes
        ]
        grants.extend(
            (
                _grant(request, variable_name=_variable("routing-2")),
                _grant(
                    request,
                    operation=NodeControlOperation.READ_STATE,
                    command_codec=None,
                ),
                _grant(request, command_codec=ControlPlaneCommandCodec.REPLACE_MAP_V1),
                _grant(request, request_id="request-2"),
                _grant(request, idempotency_key="routing-change-2"),
                _grant(request, request_digest=NodeControlRequestDigest("0" * 64)),
            )
        )
        for identity, grant in enumerate(grants):
            with self.subTest(identity=identity):
                self._assert_rejected(
                    lambda grant=grant: self._admit(
                        _token(self.private_a, grant),
                        request,
                    )
                )

        valid = _token(self.private_a, _grant(request))
        self._assert_rejected(
            lambda: self._admit(
                valid,
                request,
                route_operation=NodeControlOperation.READ_STATE,
            )
        )
        self._assert_rejected(
            lambda: self._admit(
                valid,
                request,
                route_variable=_variable("routing-2"),
            )
        )

    def test_header_and_registered_claims_are_congruent_after_maintained_admission(
        self,
    ) -> None:
        request = _request()
        cases = (
            (
                "issuer",
                _grant(request, issuer="embedded-issuer"),
                {},
                {"iss": ISSUER},
            ),
            (
                "audience",
                _grant(request, audience="embedded-audience"),
                {},
                {"aud": AUDIENCE},
            ),
            (
                "key-id",
                _grant(request, key_id="workload-key-b"),
                {"kid": "workload-key-a"},
                {},
            ),
        )
        for identity, grant, header_changes, payload_changes in cases:
            with self.subTest(identity=identity):
                token = _token(
                    self.private_a,
                    grant,
                    header_changes=header_changes,
                    payload_changes=payload_changes,
                )
                maintained_claims = jwt.decode(
                    token,
                    self.key_a.public_key_pem,
                    algorithms=["EdDSA"],
                    issuer=ISSUER,
                    audience=AUDIENCE,
                    options={
                        "verify_exp": False,
                        "verify_nbf": False,
                        "verify_iat": False,
                    },
                )
                self.assertEqual(maintained_claims["iss"], ISSUER)
                self.assertEqual(maintained_claims["aud"], AUDIENCE)
                self.assertEqual(
                    jwt.get_unverified_header(token)["kid"],
                    "workload-key-a",
                )

                jwt_calls = 0
                original_decode = jwt.decode

                def counted_decode(*args: object, **kwargs: object) -> object:
                    nonlocal jwt_calls
                    jwt_calls += 1
                    return original_decode(*args, **kwargs)

                with _replaced_attribute(jwt, "decode", counted_decode):
                    self._assert_rejected(lambda: self._admit(token, request))
                self.assertEqual(jwt_calls, 1)

    def test_route_reference_nested_text_is_exact_before_equality(self) -> None:
        request = _request()
        route_variable = _variable()
        object.__setattr__(route_variable, "value", SensitiveText("routing"))

        self._assert_rejected(
            lambda: self._admit(
                _token(self.private_a, _grant(request)),
                request,
                route_variable=route_variable,
            )
        )

    def test_key_material_is_workload_ed25519_and_snapshots_are_a_a_plus_b_b(self) -> None:
        request_a = _request()
        grant_a = _grant(request_a)
        token_a = _token(self.private_a, grant_a)
        self.assertEqual(self._admit(token_a, request_a), request_a)

        self.holder.replace(self.snapshot_a_b)
        request_b = _request(request_id="request-b", idempotency_key="change-b")
        grant_b = _grant(request_b, key_id="workload-key-b", jti="grant-b")
        token_b = _token(self.private_b, grant_b)
        self.assertEqual(self._admit(token_a, request_a), request_a)
        self.assertEqual(self._admit(token_b, request_b), request_b)

        self.holder.replace(self.snapshot_b)
        self._assert_rejected(lambda: self._admit(token_a, request_a))
        self.assertEqual(self._admit(token_b, request_b), request_b)

        malformed = DelegationPublicKey(
            "workload-key-a",
            DelegationKeyAlgorithm.ED25519,
            "-----BEGIN PUBLIC KEY-----\nnot-cryptographic-material\n-----END PUBLIC KEY-----\n",
        )
        malformed_holder = AtomicWorkloadNodeControlVerifierKeySet(self._snapshot(malformed))
        self._assert_rejected(
            lambda: self._admit(
                token_a,
                request_a,
                verifier=self._verifier(holder=malformed_holder),
            )
        )

        rsa_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        rsa_pem = rsa_private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        rsa_material = DelegationPublicKey(
            "workload-key-a",
            DelegationKeyAlgorithm.ED25519,
            rsa_pem,
        )
        rsa_holder = AtomicWorkloadNodeControlVerifierKeySet(self._snapshot(rsa_material))
        self._assert_rejected(
            lambda: self._admit(
                token_a,
                request_a,
                verifier=self._verifier(holder=rsa_holder),
            )
        )

        wrong_purpose_snapshot = self._snapshot(self.key_a)
        object.__setattr__(
            wrong_purpose_snapshot,
            "purpose",
            DelegationKeyPurpose.GATEWAY_PROBE,
        )
        wrong_purpose_holder = AtomicWorkloadNodeControlVerifierKeySet(
            wrong_purpose_snapshot
        )
        self._assert_rejected(
            lambda: self._admit(
                token_a,
                request_a,
                verifier=self._verifier(holder=wrong_purpose_holder),
            )
        )

    def test_one_admission_uses_one_complete_key_snapshot_during_replacement(self) -> None:
        request = _request()
        token = _token(self.private_a, _grant(request))
        entered = Event()
        release = Event()
        result: list[object] = []
        original_decode = jwt.decode

        def blocking_decode(*args: object, **kwargs: object) -> object:
            entered.set()
            if not release.wait(3):
                raise AssertionError("snapshot test did not release signature admission")
            return original_decode(*args, **kwargs)

        def admit() -> None:
            try:
                result.append(self._admit(token, request))
            except BaseException as error:
                result.append(error)

        with _replaced_attribute(jwt, "decode", blocking_decode):
            thread = Thread(target=admit)
            thread.start()
            self.assertTrue(entered.wait(3))
            self.holder.replace(self.snapshot_b)
            release.set()
            thread.join(3)
            self.assertFalse(thread.is_alive())

        self.assertEqual(result, [request])

    def test_errors_never_expose_credential_key_candidate_or_library_material(self) -> None:
        request = _request()
        token = _token(self.private_b, _grant(request))
        marker_values = (
            token.decode("ascii"),
            self.key_a.key_id,
            self.key_a.fingerprint_sha256,
            self.key_a.public_key_pem,
            "candidate-secret",
            "authorization",
            "Traceback",
            "InvalidSignature",
            "router",
        )
        error = self._assert_rejected(
            lambda: self._admit(
                token,
                request,
                candidate=SensitiveCandidate(),
            )
        )
        rendered = str(error) + repr(error)
        self.assertLessEqual(len(rendered.encode("utf-8")), 256)
        for marker in marker_values:
            with self.subTest(marker=marker[:32]):
                self.assertNotIn(marker, rendered)

    def test_optional_module_imports_and_installed_probe_preserve_root_laziness(self) -> None:
        module_path = PACKAGE_ROOT / "verification.py"
        self.assertTrue(module_path.is_file())
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".", 1)[0])
        self.assertIn("jwt", roots)
        self.assertNotIn("cryptography", roots)
        self.assertTrue(
            roots.isdisjoint(
                {
                    "control_plane_kit_operations",
                    "control_plane_kit_servers",
                    "fastapi",
                    "psycopg",
                    "docker",
                    "cloudflare",
                }
            )
        )

        helper = REPOSITORY_ROOT / "test_support" / "installed_verification_dependencies.py"
        helper_tree = ast.parse(helper.read_text(encoding="utf-8"), filename=str(helper))
        imported = {
            node.module
            for node in ast.walk(helper_tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        self.assertIn(VERIFICATION_MODULE, imported)

    def test_readme_and_decision_0010_assign_security_and_deferred_ownership(self) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        decision_path = (
            REPOSITORY_ROOT
            / "docs"
            / "decisions"
            / "0010-signed-workload-node-control-admission.md"
        )
        self.assertTrue(decision_path.is_file())
        decision = decision_path.read_text(encoding="utf-8")
        for required in (
            "Ed25519WorkloadNodeControlVerifier",
            "CPK-WORKLOAD-NODE-CONTROL+JWT",
            "PyJWT==2.13.0",
            "cryptography==50.0.0",
            "one trusted clock",
            "authentication precedes candidate decoding",
            "duplicate",
            "replay",
            "#1150",
            "no private key",
        ):
            with self.subTest(required=required):
                self.assertIn(required, readme + decision)


class SignedSurfaceReadVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_a = ed25519.Ed25519PrivateKey.generate()
        self.private_b = ed25519.Ed25519PrivateKey.generate()
        self.key_a = DelegationPublicKey(
            "surface-key-a",
            DelegationKeyAlgorithm.ED25519,
            _public_pem(self.private_a),
        )
        self.key_b = DelegationPublicKey(
            "surface-key-b",
            DelegationKeyAlgorithm.ED25519,
            _public_pem(self.private_b),
        )

    def _module(self):
        return importlib.import_module(VERIFICATION_MODULE)

    def _key_types(self) -> tuple[type, type]:
        module = importlib.import_module(
            "control_plane_kit_server_sdk.verifier_keys"
        )
        try:
            return (
                module.WorkloadNodeControlSurfaceReadVerifierKeySet,
                module.AtomicWorkloadNodeControlSurfaceReadVerifierKeySet,
            )
        except AttributeError:
            self.fail("surface-read verifier key types are not implemented")

    def _snapshot(self, *keys: DelegationPublicKey):
        key_set_type, _ = self._key_types()
        return key_set_type(
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
            keys,
        )

    def _holder(self, *keys: DelegationPublicKey):
        _, holder_type = self._key_types()
        return holder_type(self._snapshot(*keys))

    def _verifier(
        self,
        *,
        holder=None,
        clock=None,
        issuer: str = ISSUER,
        audience: str = AUDIENCE,
    ):
        module = self._module()
        try:
            verifier_type = module.Ed25519WorkloadNodeControlSurfaceReadVerifier
        except AttributeError:
            self.fail("signed surface-read verifier is not implemented")
        return verifier_type(
            self._holder(self.key_a) if holder is None else holder,
            expected_issuer=issuer,
            expected_audience=audience,
            clock=(lambda: NOW) if clock is None else clock,
        )

    def _admit(
        self,
        token: object,
        request: NodeControlSurfaceReadRequest,
        *,
        verifier=None,
        route_kind: object = _UNSET,
        candidate: object = None,
    ) -> NodeControlSurfaceReadRequest:
        return (verifier or self._verifier()).admit(
            token,
            route_kind=request.kind if route_kind is _UNSET else route_kind,
            candidate=candidate,
        )

    def _assert_rejected(self, operation) -> BaseException:
        module = self._module()
        try:
            error_type = module.WorkloadNodeControlSurfaceReadVerificationError
        except AttributeError:
            self.fail("surface-read verification error is not implemented")
        with self.assertRaises(error_type) as raised:
            operation()
        self.assertEqual(str(raised.exception), SURFACE_ERROR_MESSAGE)
        self.assertEqual(
            repr(raised.exception),
            "WorkloadNodeControlSurfaceReadVerificationError("
            f"{SURFACE_ERROR_MESSAGE!r})",
        )
        self.assertEqual(vars(raised.exception), {})
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        return raised.exception

    def _assert_before_maintained_admission(
        self,
        token: object,
        request: NodeControlSurfaceReadRequest,
        *,
        route_kind: object = _UNSET,
        candidate: object = None,
    ) -> None:
        calls = {"jwt": 0, "grant": 0, "snapshot": 0, "clock": 0}
        _, holder_type = self._key_types()

        def forbidden_jwt(*_args: object, **_kwargs: object) -> object:
            calls["jwt"] += 1
            raise AssertionError("maintained signature admission was reached")

        def forbidden_grant(*_args: object, **_kwargs: object) -> object:
            calls["grant"] += 1
            raise AssertionError("signed grant decoding was reached")

        def forbidden_snapshot(*_args: object, **_kwargs: object) -> object:
            calls["snapshot"] += 1
            raise AssertionError("verification key snapshot was reached")

        def forbidden_clock() -> int:
            calls["clock"] += 1
            raise AssertionError("trusted clock was reached")

        holder = self._holder(self.key_a)
        verifier = self._verifier(holder=holder, clock=forbidden_clock)
        with _replaced_attribute(jwt, "decode", forbidden_jwt), _replaced_attribute(
            DelegatedWorkloadNodeControlSurfaceReadGrantCodec,
            "decode",
            forbidden_grant,
        ), _replaced_attribute(holder_type, "snapshot", forbidden_snapshot):
            self._assert_rejected(
                lambda: self._admit(
                    token,
                    request,
                    verifier=verifier,
                    route_kind=route_kind,
                    candidate=candidate,
                )
            )
        self.assertEqual(calls, {"jwt": 0, "grant": 0, "snapshot": 0, "clock": 0})

    def test_public_optional_module_and_root_exports_are_exact(self) -> None:
        module = self._module()
        self.assertEqual(
            module.__all__,
            [
                "Ed25519WorkloadNodeControlSurfaceReadVerifier",
                "Ed25519WorkloadNodeControlVerifier",
                "WorkloadNodeControlSurfaceReadVerificationError",
                "WorkloadNodeControlVerificationError",
            ],
        )
        self.assertEqual(
            module.Ed25519WorkloadNodeControlSurfaceReadVerifier.__module__,
            VERIFICATION_MODULE,
        )
        root = importlib.import_module("control_plane_kit_server_sdk")
        self.assertNotIn(
            "Ed25519WorkloadNodeControlSurfaceReadVerifier",
            root.__all__,
        )
        self.assertFalse(
            hasattr(root, "Ed25519WorkloadNodeControlSurfaceReadVerifier")
        )

    def test_constructor_and_stateless_shape_are_exact_slotted_and_redacted(self) -> None:
        verifier = self._verifier()
        verifier_type = type(verifier)
        self.assertEqual(
            verifier_type.__slots__,
            ("_holder", "_expected_issuer", "_expected_audience", "_clock"),
        )
        self.assertFalse(hasattr(verifier, "__dict__"))
        self.assertEqual(
            repr(verifier),
            "Ed25519WorkloadNodeControlSurfaceReadVerifier()",
        )

        command_holder = AtomicWorkloadNodeControlVerifierKeySet(
            WorkloadNodeControlVerifierKeySet(
                DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
                (self.key_a,),
            )
        )
        for keyword, value in (
            ("holder", command_holder),
            ("issuer", SensitiveText(ISSUER)),
            ("audience", SensitiveText(AUDIENCE)),
            ("clock", SensitiveCandidate()),
        ):
            with self.subTest(keyword=keyword):
                arguments = {
                    "holder": self._holder(self.key_a),
                    "issuer": ISSUER,
                    "audience": AUDIENCE,
                    "clock": lambda: NOW,
                }
                arguments[keyword] = value
                with self.assertRaises((TypeError, ValueError)) as raised:
                    verifier_type(
                        arguments["holder"],
                        expected_issuer=arguments["issuer"],
                        expected_audience=arguments["audience"],
                        clock=arguments["clock"],
                    )
                self.assertIsNone(raised.exception.__cause__)
                self.assertIsNone(raised.exception.__context__)
                self.assertNotIn("nested-secret", str(raised.exception))
                self.assertNotIn("candidate-secret", str(raised.exception))

    def test_both_read_kinds_return_only_the_exact_reconstructed_request(self) -> None:
        for kind in NodeControlSurfaceReadKind:
            with self.subTest(kind=kind):
                request = _surface_request(kind)
                token = _surface_token(self.private_a, _surface_grant(request))
                admitted = self._admit(token, request)
                self.assertIs(type(admitted), NodeControlSurfaceReadRequest)
                self.assertEqual(admitted, request)
                self.assertIsNot(admitted, request)
                self.assertEqual(admitted.canonical_bytes(), request.canonical_bytes())

    def test_trusted_route_and_no_payload_inputs_reject_before_all_collaborators(self) -> None:
        request = _surface_request()
        token = _surface_token(self.private_a, _surface_grant(request))
        for route_kind in (
            None,
            "capabilities",
            NodeControlOperation.READ_STATE,
            SensitiveCandidate(),
            ExplodingReprCandidate(),
        ):
            with self.subTest(route_kind_type=type(route_kind).__name__):
                self._assert_before_maintained_admission(
                    token,
                    request,
                    route_kind=route_kind,
                )
        for candidate in (
            b"",
            b"{}",
            "",
            0,
            False,
            SensitiveCandidate(),
            ExplodingReprCandidate(),
        ):
            with self.subTest(candidate_type=type(candidate).__name__):
                self._assert_before_maintained_admission(
                    token,
                    request,
                    candidate=candidate,
                )

    def test_maximum_valid_credential_and_every_independent_bound(self) -> None:
        maximum_text = lambda first, tail, size: first + tail * (size - 1)
        target = NodeControlTarget(
            workspace_id=_reference(
                NodeControlGraphReferenceRole.WORKSPACE,
                maximum_text("W", "w", 128),
            ),
            graph_revision=_reference(
                NodeControlGraphReferenceRole.GRAPH_REVISION,
                maximum_text("G", "g", 128),
            ),
            node_id=_reference(
                NodeControlGraphReferenceRole.NODE,
                maximum_text("N", "n", 128),
            ),
            provider_socket_name=_reference(
                NodeControlGraphReferenceRole.PROVIDER_SOCKET,
                maximum_text("S", "s", 128),
            ),
        )
        request = _surface_request(
            target=target,
            declaration_identity=WorkloadNodeControlSurfaceDeclarationIdentity(
                "f" * 64
            ),
            request_id=maximum_text("R", "r", 128),
        )
        private_key = ed25519.Ed25519PrivateKey.generate()
        key_id = maximum_text("k", "k", 128)
        key = DelegationPublicKey(
            key_id,
            DelegationKeyAlgorithm.ED25519,
            _public_pem(private_key),
        )
        maximum_epoch = 2**53 - 1
        grant = _surface_grant(
            request,
            key_id=key_id,
            issuer=maximum_text("I", "i", 256),
            audience=maximum_text("A", "a", 256),
            issued_at=maximum_epoch - 300,
            not_before=maximum_epoch - 300,
            expires_at=maximum_epoch,
            jti=maximum_text("J", "j", 128),
        )
        token = _surface_token(private_key, grant)
        segments = token.split(b".")

        self.assertEqual(tuple(map(len, segments)), (271, 3_679, 86))
        self.assertEqual(len(token), 4_038)
        self.assertLessEqual(len(token), MAX_SURFACE_CREDENTIAL_BYTES)
        self.assertLessEqual(len(segments[0]), MAX_SURFACE_HEADER_SEGMENT_BYTES)
        self.assertLessEqual(len(segments[1]), MAX_SURFACE_PAYLOAD_SEGMENT_BYTES)
        self.assertLessEqual(len(segments[2]), MAX_SURFACE_SIGNATURE_SEGMENT_BYTES)
        verifier = self._verifier(
            holder=self._holder(key),
            issuer=grant.issuer,
            audience=grant.audience,
            clock=lambda: maximum_epoch - 1,
        )
        self.assertEqual(self._admit(token, request, verifier=verifier), request)

        independent_edges = (
            b"A" * MAX_SURFACE_HEADER_SEGMENT_BYTES
            + b"."
            + b"A" * 3_480
            + b"."
            + b"A" * MAX_SURFACE_SIGNATURE_SEGMENT_BYTES,
            b"A" * 514 + b".e30." + b"A" * 86,
            b"e30." + b"A" * 3_842 + b"." + b"A" * 86,
            b"e30.e30." + b"A" * 130,
        )
        for identity, candidate_token in enumerate(independent_edges):
            with self.subTest(edge=identity):
                decode_calls = 0

                def forbidden_decode(*_args: object, **_kwargs: object) -> bytes:
                    nonlocal decode_calls
                    decode_calls += 1
                    raise AssertionError("base64 decoding was reached")

                with _replaced_attribute(base64, "b64decode", forbidden_decode):
                    self._assert_before_maintained_admission(
                        candidate_token,
                        request,
                    )
                self.assertEqual(decode_calls, 0)

    def test_compact_and_structural_profiles_reject_before_maintained_admission(self) -> None:
        request = _surface_request()
        grant = _surface_grant(request)
        malformed = (
            b"",
            b"a.b",
            b"a.b.c.d",
            b"a=.b.c",
            b"a.b.%%",
            b"a.b.c\xff",
        )
        for token in malformed:
            with self.subTest(token=token[:12]):
                self._assert_before_maintained_admission(token, request)

        header = _surface_header()
        payload = _surface_payload(grant)
        grant_descriptor = grant.descriptor()
        target_descriptor = grant.target.descriptor()

        header_bytes = _json_with_pad_bits(header)
        payload_bytes = _json_with_pad_bits(payload)
        canonical = _signed_compact(
            self.private_a,
            header_bytes=header_bytes,
            payload_bytes=payload_bytes,
        )
        header_segment, payload_segment, signature_segment = canonical.split(b".")
        noncanonical_header = _noncanonical_tail(header_segment)
        noncanonical_payload = _noncanonical_tail(payload_segment)
        noncanonical_tokens = (
            noncanonical_header
            + b"."
            + payload_segment
            + b"."
            + _b64url(
                self.private_a.sign(
                    noncanonical_header + b"." + payload_segment
                )
            ),
            header_segment
            + b"."
            + noncanonical_payload
            + b"."
            + _b64url(
                self.private_a.sign(
                    header_segment + b"." + noncanonical_payload
                )
            ),
            b".".join(
                (
                    header_segment,
                    payload_segment,
                    _noncanonical_tail(signature_segment),
                )
            ),
        )
        for identity, token in enumerate(noncanonical_tokens):
            with self.subTest(noncanonical=identity):
                self._assert_before_maintained_admission(token, request)

        missing_unknown_wrong: list[tuple[bytes, bytes]] = [
            (
                _json_value({key: value for key, value in header.items() if key != "typ"}),
                _json_value(payload),
            ),
            (_json_value({**header, "unknown": 1}), _json_value(payload)),
            (b"[]", _json_value(payload)),
            (_json_value({**header, "kid": 7}), _json_value(payload)),
            (
                _json_value(header),
                _json_value({key: value for key, value in payload.items() if key != "jti"}),
            ),
            (_json_value(header), _json_value({**payload, "unknown": 1})),
            (_json_value(header), b"[]"),
            (_json_value(header), _json_value({**payload, "iss": 7})),
            (
                _json_value(header),
                _json_value(
                    {
                        **payload,
                        SURFACE_PAYLOAD_KEY: {
                            key: value
                            for key, value in grant_descriptor.items()
                            if key != "request_digest"
                        },
                    }
                ),
            ),
            (
                _json_value(header),
                _json_value(
                    {
                        **payload,
                        SURFACE_PAYLOAD_KEY: {**grant_descriptor, "unknown": 1},
                    }
                ),
            ),
            (
                _json_value(header),
                _json_value({**payload, SURFACE_PAYLOAD_KEY: []}),
            ),
            (
                _json_value(header),
                _json_value(
                    {
                        **payload,
                        SURFACE_PAYLOAD_KEY: {
                            **grant_descriptor,
                            "issued_at": "100",
                        },
                    }
                ),
            ),
            (
                _json_value(header),
                _json_value(
                    {
                        **payload,
                        SURFACE_PAYLOAD_KEY: {
                            **grant_descriptor,
                            "target": {
                                key: value
                                for key, value in target_descriptor.items()
                                if key != "node_id"
                            },
                        },
                    }
                ),
            ),
            (
                _json_value(header),
                _json_value(
                    {
                        **payload,
                        SURFACE_PAYLOAD_KEY: {
                            **grant_descriptor,
                            "target": {**target_descriptor, "unknown": 1},
                        },
                    }
                ),
            ),
            (
                _json_value(header),
                _json_value(
                    {
                        **payload,
                        SURFACE_PAYLOAD_KEY: {
                            **grant_descriptor,
                            "target": [],
                        },
                    }
                ),
            ),
            (
                _json_value(header),
                _json_value(
                    {
                        **payload,
                        SURFACE_PAYLOAD_KEY: {
                            **grant_descriptor,
                            "target": {**target_descriptor, "node_id": 7},
                        },
                    }
                ),
            ),
        ]
        for identity, (candidate_header, candidate_payload) in enumerate(
            missing_unknown_wrong
        ):
            with self.subTest(closed_profile=identity):
                token = _signed_compact(
                    self.private_a,
                    header_bytes=candidate_header,
                    payload_bytes=candidate_payload,
                )
                self._assert_before_maintained_admission(token, request)

        duplicates: list[tuple[bytes, bytes]] = []
        for key in header:
            duplicates.append(
                (_raw_object(_duplicate_pair(header, key)), _json_value(payload))
            )
        for key in payload:
            duplicates.append(
                (_json_value(header), _raw_object(_duplicate_pair(payload, key)))
            )
        for key in grant_descriptor:
            raw_grant = _raw_object(_duplicate_pair(grant_descriptor, key))
            duplicates.append(
                (
                    _json_value(header),
                    _raw_object(
                        [
                            (
                                name,
                                RawJson(raw_grant)
                                if name == SURFACE_PAYLOAD_KEY
                                else value,
                            )
                            for name, value in payload.items()
                        ]
                    ),
                )
            )
        for key in target_descriptor:
            raw_target = _raw_object(_duplicate_pair(target_descriptor, key))
            raw_grant = _raw_object(
                [
                    (
                        name,
                        RawJson(raw_target) if name == "target" else value,
                    )
                    for name, value in grant_descriptor.items()
                ]
            )
            duplicates.append(
                (
                    _json_value(header),
                    _raw_object(
                        [
                            (
                                name,
                                RawJson(raw_grant)
                                if name == SURFACE_PAYLOAD_KEY
                                else value,
                            )
                            for name, value in payload.items()
                        ]
                    ),
                )
            )
        for identity, (header_bytes, payload_bytes) in enumerate(duplicates):
            with self.subTest(duplicate=identity):
                token = _signed_compact(
                    self.private_a,
                    header_bytes=header_bytes,
                    payload_bytes=payload_bytes,
                )
                self._assert_before_maintained_admission(token, request)

        excessive_depth = (
            b"[" * (MAX_STRUCTURAL_JSON_DEPTH + 1)
            + b"0"
            + b"]" * (MAX_STRUCTURAL_JSON_DEPTH + 1)
        )
        deep_payload = _raw_object(
            [
                (name, RawJson(excessive_depth) if name == SURFACE_PAYLOAD_KEY else value)
                for name, value in payload.items()
            ]
        )
        many_members = _raw_object(
            [(f"m{index}", index) for index in range(MAX_STRUCTURAL_JSON_MEMBERS + 1)]
        )
        for payload_bytes in (deep_payload, many_members):
            token = _signed_compact(
                self.private_a,
                header_bytes=_json_value(header),
                payload_bytes=payload_bytes,
            )
            self._assert_before_maintained_admission(token, request)

    def test_profile_algorithm_signature_and_authority_families_are_disjoint(self) -> None:
        request = _surface_request()
        grant = _surface_grant(request)
        for header_changes, payload_changes in (
            ({"alg": "HS256"}, None),
            ({"typ": TOKEN_TYPE}, None),
            (None, {"workload_node_control": grant.descriptor()}),
        ):
            token = _surface_token(
                self.private_a,
                grant,
                header_changes=header_changes,
                payload_changes=payload_changes,
            )
            self._assert_before_maintained_admission(token, request)

        self._assert_rejected(
            lambda: self._admit(
                _surface_token(self.private_b, grant),
                request,
            )
        )
        wrong_purpose = replace(
            grant,
            purpose=DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
        )
        self._assert_rejected(
            lambda: self._admit(
                _surface_token(self.private_a, wrong_purpose),
                request,
            )
        )

        shared_private = ed25519.Ed25519PrivateKey.generate()
        shared_key = DelegationPublicKey(
            "shared-key",
            DelegationKeyAlgorithm.ED25519,
            _public_pem(shared_private),
        )
        surface_grant = _surface_grant(request, key_id="shared-key")
        command_request = _request(NodeControlOperation.READ_STATE)
        command_grant = _grant(command_request, key_id="shared-key")
        surface_verifier = self._verifier(holder=self._holder(shared_key))
        command_holder = AtomicWorkloadNodeControlVerifierKeySet(
            WorkloadNodeControlVerifierKeySet(
                DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
                (shared_key,),
            )
        )
        command_verifier = self._module().Ed25519WorkloadNodeControlVerifier(
            command_holder,
            expected_issuer=ISSUER,
            expected_audience=AUDIENCE,
            clock=lambda: NOW,
        )
        self._assert_rejected(
            lambda: self._admit(
                _token(shared_private, command_grant),
                request,
                verifier=surface_verifier,
            )
        )
        with self.assertRaises(self._module().WorkloadNodeControlVerificationError):
            command_verifier.admit(
                _surface_token(shared_private, surface_grant),
                route_operation=command_request.operation,
                route_variable=command_request.variable_name,
                candidate=None,
            )

    def test_authenticated_outer_inner_congruence_rejects_after_pyjwt(self) -> None:
        request = _surface_request()
        grant = _surface_grant(request)
        original_decode = jwt.decode
        cases: list[tuple[bytes, object, str, str]] = []

        cases.append(
            (
                _surface_token(
                    self.private_b,
                    grant,
                    header_changes={"kid": self.key_b.key_id},
                ),
                self._holder(self.key_a, self.key_b),
                ISSUER,
                AUDIENCE,
            )
        )
        for field, outer_value in (
            ("iss", "outer-issuer"),
            ("aud", "outer-audience"),
            ("iat", 101),
            ("nbf", 101),
            ("exp", 201),
            ("jti", "outer-jti"),
        ):
            cases.append(
                (
                    _surface_token(
                        self.private_a,
                        grant,
                        payload_changes={field: outer_value},
                    ),
                    self._holder(self.key_a),
                    outer_value if field == "iss" else ISSUER,
                    outer_value if field == "aud" else AUDIENCE,
                )
            )

        verification_module = self._module()
        for identity, (token, holder, issuer, audience) in enumerate(cases):
            calls = {"jwt": 0, "clock": 0, "request": 0}

            def counted_decode(*args: object, **kwargs: object) -> object:
                calls["jwt"] += 1
                return original_decode(*args, **kwargs)

            def forbidden_clock() -> int:
                calls["clock"] += 1
                raise AssertionError("trusted clock was reached")

            def forbidden_request(*_args: object, **_kwargs: object) -> object:
                calls["request"] += 1
                raise AssertionError("request construction was reached")

            verifier = self._verifier(
                holder=holder,
                issuer=issuer,
                audience=audience,
                clock=forbidden_clock,
            )

            with self.subTest(identity=identity), _replaced_attribute(
                jwt,
                "decode",
                counted_decode,
            ), _replaced_attribute(
                verification_module,
                "NodeControlSurfaceReadRequest",
                forbidden_request,
            ):
                self._assert_rejected(
                    lambda: self._admit(token, request, verifier=verifier)
                )
                self.assertEqual(calls, {"jwt": 1, "clock": 0, "request": 0})

    def test_maintained_admission_options_key_rotation_and_failure_order_are_exact(self) -> None:
        request_a = _surface_request()
        grant_a = _surface_grant(request_a)
        token_a = _surface_token(self.private_a, grant_a)
        holder = self._holder(self.key_a)
        verifier = self._verifier(holder=holder)
        captured: list[tuple[tuple[object, ...], dict[str, object]]] = []
        original_decode = jwt.decode

        def captured_decode(*args: object, **kwargs: object) -> object:
            captured.append((args, kwargs))
            return original_decode(*args, **kwargs)

        with _replaced_attribute(jwt, "decode", captured_decode):
            self.assertEqual(
                self._admit(token_a, request_a, verifier=verifier),
                request_a,
            )
        self.assertEqual(len(captured), 1)
        args, kwargs = captured[0]
        self.assertIs(args[0], token_a)
        self.assertEqual(args[1], self.key_a.public_key_pem)
        self.assertEqual(kwargs["algorithms"], ["EdDSA"])
        self.assertEqual(kwargs["issuer"], ISSUER)
        self.assertEqual(kwargs["audience"], AUDIENCE)
        self.assertEqual(
            kwargs["options"],
            {
                "require": ["iss", "aud", "iat", "nbf", "exp", "jti"],
                "verify_exp": False,
                "verify_nbf": False,
                "verify_iat": False,
                "strict_aud": True,
            },
        )

        request_b = _surface_request(
            NodeControlSurfaceReadKind.STATUS,
            request_id="surface-read-b",
        )
        grant_b = _surface_grant(
            request_b,
            key_id=self.key_b.key_id,
            jti="surface-grant-b",
        )
        token_b = _surface_token(self.private_b, grant_b)
        holder.replace(self._snapshot(self.key_a, self.key_b))
        self.assertEqual(self._admit(token_a, request_a, verifier=verifier), request_a)
        self.assertEqual(self._admit(token_b, request_b, verifier=verifier), request_b)
        holder.replace(self._snapshot(self.key_b))
        self._assert_rejected(
            lambda: self._admit(token_a, request_a, verifier=verifier)
        )
        self.assertEqual(self._admit(token_b, request_b, verifier=verifier), request_b)

        malformed = DelegationPublicKey(
            self.key_a.key_id,
            DelegationKeyAlgorithm.ED25519,
            "-----BEGIN PUBLIC KEY-----\nnot-cryptographic-material\n"
            "-----END PUBLIC KEY-----\n",
        )
        self._assert_rejected(
            lambda: self._admit(
                token_a,
                request_a,
                verifier=self._verifier(holder=self._holder(malformed)),
            )
        )
        rsa_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        rsa_pem = rsa_private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        rsa_material = DelegationPublicKey(
            self.key_a.key_id,
            DelegationKeyAlgorithm.ED25519,
            rsa_pem,
        )
        self._assert_rejected(
            lambda: self._admit(
                token_a,
                request_a,
                verifier=self._verifier(holder=self._holder(rsa_material)),
            )
        )
        wrong_purpose = self._snapshot(self.key_a)
        object.__setattr__(
            wrong_purpose,
            "purpose",
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
        )
        _, surface_holder_type = self._key_types()
        self._assert_rejected(
            lambda: self._admit(
                token_a,
                request_a,
                verifier=self._verifier(
                    holder=surface_holder_type(wrong_purpose)
                ),
            )
        )

        calls = {"jwt": 0, "grant": 0, "clock": 0}

        def counted_jwt(*_args: object, **_kwargs: object) -> object:
            calls["jwt"] += 1
            raise AssertionError("maintained signature admission was reached")

        def counted_grant(*_args: object, **_kwargs: object) -> object:
            calls["grant"] += 1
            raise AssertionError("signed grant decoding was reached")

        def counted_clock() -> int:
            calls["clock"] += 1
            raise AssertionError("trusted clock was reached")

        unknown = _surface_token(
            self.private_a,
            grant_a,
            header_changes={"kid": "unknown-key"},
        )
        with _replaced_attribute(jwt, "decode", counted_jwt), _replaced_attribute(
            DelegatedWorkloadNodeControlSurfaceReadGrantCodec,
            "decode",
            counted_grant,
        ):
            self._assert_rejected(
                lambda: self._admit(
                    unknown,
                    request_a,
                    verifier=self._verifier(
                        holder=self._holder(self.key_a),
                        clock=counted_clock,
                    ),
                )
            )
        self.assertEqual(calls, {"jwt": 0, "grant": 0, "clock": 0})

        calls = {"jwt": 0, "grant": 0, "clock": 0}

        def failing_jwt(*args: object, **kwargs: object) -> object:
            calls["jwt"] += 1
            return original_decode(*args, **kwargs)

        with _replaced_attribute(jwt, "decode", failing_jwt), _replaced_attribute(
            DelegatedWorkloadNodeControlSurfaceReadGrantCodec,
            "decode",
            counted_grant,
        ):
            self._assert_rejected(
                lambda: self._admit(
                    _surface_token(self.private_b, grant_a),
                    request_a,
                    verifier=self._verifier(
                        holder=self._holder(self.key_a),
                        clock=counted_clock,
                    ),
                )
            )
        self.assertEqual(calls, {"jwt": 1, "grant": 0, "clock": 0})

    def test_foreign_authority_families_never_substitute(self) -> None:
        request = _surface_request()
        shared_private = ed25519.Ed25519PrivateKey.generate()
        shared_key = DelegationPublicKey(
            "shared-key",
            DelegationKeyAlgorithm.ED25519,
            _public_pem(shared_private),
        )
        verifier = self._verifier(holder=self._holder(shared_key))
        command_requests = (
            _request(NodeControlOperation.READ_STATE),
            _request(NodeControlOperation.APPLY_COMMAND),
        )
        foreign = [
            _token(
                shared_private,
                _grant(command_request, key_id="shared-key"),
            )
            for command_request in command_requests
        ]
        outer = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": 100,
            "nbf": 100,
            "exp": 200,
            "jti": "foreign-grant",
        }
        for token_type, member in (
            ("CPK-GATEWAY-PROBE+JWT", "gateway_probe_grant"),
            ("CPK-GATEWAY-TRANSIT+JWT", "gateway_transit_grant"),
        ):
            foreign.append(
                _signed_compact(
                    shared_private,
                    header_bytes=_json_value(
                        {"alg": "EdDSA", "kid": "shared-key", "typ": token_type}
                    ),
                    payload_bytes=_json_value(
                        {**outer, member: {"authority": "foreign"}}
                    ),
                )
            )
        foreign.extend((b"operator-bearer", b"static-bearer"))

        for identity, token in enumerate(foreign):
            with self.subTest(authority=identity):
                self._assert_rejected(
                    lambda token=token: self._admit(
                        token,
                        request,
                        verifier=verifier,
                    )
                )

    def test_exact_request_binding_route_time_one_clock_and_no_replay_state(self) -> None:
        request = _surface_request()
        target_mismatches = (
            _target(
                workspace_id=_reference(
                    NodeControlGraphReferenceRole.WORKSPACE,
                    "other-workspace",
                )
            ),
            _target(
                graph_revision=_reference(
                    NodeControlGraphReferenceRole.GRAPH_REVISION,
                    "other-revision",
                )
            ),
            _target(
                node_id=_reference(
                    NodeControlGraphReferenceRole.NODE,
                    "other-node",
                )
            ),
            _target(
                provider_socket_name=_reference(
                    NodeControlGraphReferenceRole.PROVIDER_SOCKET,
                    "other-socket",
                )
            ),
        )
        mismatches = tuple(
            _surface_grant(request, target=target)
            for target in target_mismatches
        ) + (
            _surface_grant(request, kind=NodeControlSurfaceReadKind.STATUS),
            _surface_grant(
                request,
                declaration_identity=WorkloadNodeControlSurfaceDeclarationIdentity("e" * 64),
            ),
            _surface_grant(request, request_id="other-request"),
            _surface_grant(
                request,
                request_digest=NodeControlSurfaceReadRequestDigest("0" * 64),
            ),
        )
        for identity, grant in enumerate(mismatches):
            with self.subTest(mismatch=identity):
                self._assert_rejected(
                    lambda grant=grant: self._admit(
                        _surface_token(self.private_a, grant),
                        request,
                    )
                )

        valid_grant = _surface_grant(request)
        token = _surface_token(self.private_a, valid_grant)
        self.assertEqual(
            self._admit(
                token,
                request,
                verifier=self._verifier(clock=lambda: valid_grant.not_before),
            ),
            request,
        )
        clock_calls = 0

        def clock() -> int:
            nonlocal clock_calls
            clock_calls += 1
            return NOW

        verifier = self._verifier(clock=clock)
        self.assertEqual(self._admit(token, request, verifier=verifier), request)
        self.assertEqual(self._admit(token, request, verifier=verifier), request)
        self.assertEqual(clock_calls, 2)

        for now in (99, 200, -1, 2**53, True, SensitiveCandidate()):
            with self.subTest(now=type(now).__name__ if not isinstance(now, int) else now):
                self._assert_rejected(
                    lambda now=now: self._admit(
                        token,
                        request,
                        verifier=self._verifier(clock=lambda: now),
                    )
                )
        self._assert_rejected(
            lambda: self._admit(
                token,
                request,
                route_kind=NodeControlSurfaceReadKind.STATUS,
            )
        )

        for field, value in (
            ("profile", "other-surface-read-grant.v1"),
            ("canonicalization", "other-canonicalization.v1"),
        ):
            descriptor = valid_grant.descriptor()
            descriptor[field] = value
            payload = _surface_payload(valid_grant)
            payload[SURFACE_PAYLOAD_KEY] = descriptor
            invalid_token = _signed_compact(
                self.private_a,
                header_bytes=_json_value(_surface_header(valid_grant.key_id)),
                payload_bytes=_json_value(payload),
            )
            with self.subTest(field=field):
                self._assert_rejected(
                    lambda invalid_token=invalid_token: self._admit(
                        invalid_token,
                        request,
                    )
                )

    def test_one_admission_uses_one_complete_surface_key_snapshot(self) -> None:
        request = _surface_request()
        token = _surface_token(self.private_a, _surface_grant(request))
        holder = self._holder(self.key_a)
        entered = Event()
        release = Event()
        result: list[object] = []
        original_decode = jwt.decode

        def blocking_decode(*args: object, **kwargs: object) -> object:
            entered.set()
            if not release.wait(3):
                raise AssertionError("surface snapshot test did not release")
            return original_decode(*args, **kwargs)

        def admit() -> None:
            try:
                result.append(
                    self._admit(
                        token,
                        request,
                        verifier=self._verifier(holder=holder),
                    )
                )
            except BaseException as error:
                result.append(error)

        with _replaced_attribute(jwt, "decode", blocking_decode):
            thread = Thread(target=admit)
            thread.start()
            self.assertTrue(entered.wait(3))
            holder.replace(self._snapshot(self.key_b))
            release.set()
            thread.join(3)
            self.assertFalse(thread.is_alive())
        self.assertEqual(result, [request])

    def test_representations_errors_and_source_exclude_sensitive_or_outer_work(self) -> None:
        request = _surface_request()
        token = _surface_token(self.private_a, _surface_grant(request))
        holder = self._holder(self.key_a)
        verifier = self._verifier(holder=holder)
        key_set = holder.snapshot()
        self.assertEqual(
            repr(verifier),
            "Ed25519WorkloadNodeControlSurfaceReadVerifier()",
        )
        for rendered in (repr(verifier), repr(key_set), repr(holder)):
            for marker in (
                ISSUER,
                AUDIENCE,
                self.key_a.key_id,
                self.key_a.fingerprint_sha256,
                self.key_a.public_key_pem,
                request.request_id,
                request.declaration_identity.value,
                request.target.node_id.value,
            ):
                self.assertNotIn(marker, rendered)

        errors: list[BaseException] = []
        errors.append(
            self._assert_rejected(
                lambda: self._admit(
                    token,
                    request,
                    verifier=verifier,
                    candidate=SensitiveCandidate(),
                )
            )
        )

        def failing_jwt(*_args: object, **_kwargs: object) -> object:
            raise RuntimeError(
                "InvalidSignature authorization: Bearer crypto-secret"
            )

        with _replaced_attribute(jwt, "decode", failing_jwt):
            errors.append(
                self._assert_rejected(
                    lambda: self._admit(token, request, verifier=verifier)
                )
            )

        def failing_grant(*_args: object, **_kwargs: object) -> object:
            raise RuntimeError("credential=grant-secret target=router")

        with _replaced_attribute(
            DelegatedWorkloadNodeControlSurfaceReadGrantCodec,
            "decode",
            failing_grant,
        ):
            errors.append(
                self._assert_rejected(
                    lambda: self._admit(token, request, verifier=verifier)
                )
            )

        for error in errors:
            rendered_error = str(error) + repr(error)
            self.assertLessEqual(len(rendered_error.encode("utf-8")), 256)
            for marker in (
                token.decode("ascii"),
                "surface-grant-1",
                self.key_a.key_id,
                self.key_a.fingerprint_sha256,
                self.key_a.public_key_pem,
                ISSUER,
                AUDIENCE,
                "candidate-secret",
                "crypto-secret",
                "grant-secret",
                "Traceback",
                "InvalidSignature",
                request.request_id,
                request.declaration_identity.value,
                request.target.node_id.value,
            ):
                self.assertNotIn(marker, rendered_error)

        module_path = PACKAGE_ROOT / "verification.py"
        source = module_path.read_text(encoding="utf-8")
        for excluded in (
            "fastapi",
            "NodeControlSurfaceCapabilitiesResult",
            "NodeControlSurfaceStatusResult",
            "NodeControlSurfaceRegistryCoverage",
            "ControlPlaneVariable",
            "_replay",
        ):
            self.assertNotIn(excluded, source)
        tree = ast.parse(source, filename=str(module_path))
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
        self.assertTrue(
            imported_roots.isdisjoint(
                {
                    "control_plane_kit_operations",
                    "control_plane_kit_servers",
                    "fastapi",
                    "psycopg",
                    "docker",
                    "cloudflare",
                }
            )
        )

    def test_docs_describe_stateless_credential_admission_and_1507_handoff(self) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        decision_path = (
            REPOSITORY_ROOT
            / "docs"
            / "decisions"
            / "0012-signed-surface-read-admission.md"
        )
        self.assertTrue(decision_path.is_file())
        decision = decision_path.read_text(encoding="utf-8")
        for required in (
            "Ed25519WorkloadNodeControlSurfaceReadVerifier",
            SURFACE_TOKEN_TYPE,
            SURFACE_PAYLOAD_KEY,
            "4,096",
            "3,840",
            "stateless",
            "may be admitted again",
            "#1507",
            "no private key",
            "no HTTP",
            "no registry",
        ):
            with self.subTest(required=required):
                self.assertIn(required, readme + decision)


if __name__ == "__main__":
    unittest.main()
