"""SDK-owned signed health admission; no callback, HTTP or provider effects."""
from dataclasses import replace
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import ed25519

import control_plane_kit_core as core
import control_plane_kit_server_sdk as sdk
from control_plane_kit_server_sdk import verification
from tests import test_verification as fixtures


TOKEN_TYPE = "CPK-WORKLOAD-NODE-HEALTH-READ+JWT"
PAYLOAD_KEY = "workload_node_health_read"


class SignedHealthReadVerificationTests(unittest.TestCase):
    def setUp(self):
        self.private = ed25519.Ed25519PrivateKey.generate()
        self.other_private = ed25519.Ed25519PrivateKey.generate()
        self.key = core.DelegationPublicKey(
            "health-key-a", core.DelegationKeyAlgorithm.ED25519,
            fixtures._public_pem(self.private),
        )
        self.other_key = core.DelegationPublicKey(
            "health-key-b", core.DelegationKeyAlgorithm.ED25519,
            fixtures._public_pem(self.other_private),
        )
        self.target = fixtures._target()
        self.runtime = core.NodeControlGraphReference(
            core.NodeControlGraphReferenceRole.RUNTIME, "runtime-a",
        )
        self.declaration = core.WorkloadNodeControlSurfaceDeclaration(
            core.WorkloadNodeControlSurfaceDescriptor(
                self.target.provider_socket_name, (),
                health_reads=(core.NodeHealthReadKind.LIVENESS, core.NodeHealthReadKind.READINESS),
            ),
            profile=core.WorkloadNodeControlSurfaceDeclarationProfile.V2,
        )
        self.request = core.NodeHealthReadRequest(
            self.target, self.runtime, core.NodeHealthReadKind.READINESS,
            self.declaration.identity(), "health-observation-a",
        )
        self.holder = sdk.AtomicWorkloadNodeHealthReadVerifierKeySet(self.snapshot(self.key))
        self.clock_calls = 0

    def clock(self):
        self.clock_calls += 1
        return 150

    def snapshot(self, *keys):
        return sdk.WorkloadNodeHealthReadVerifierKeySet(
            core.DelegationKeyPurpose.WORKLOAD_NODE_HEALTH_READ, tuple(keys),
        )

    def verifier(self, **changes):
        return verification.Ed25519WorkloadNodeHealthReadVerifier(**{
            "holder": self.holder, "expected_issuer": fixtures.ISSUER,
            "expected_audience": fixtures.AUDIENCE, "clock": self.clock, **changes,
        })

    def grant(self, request=None, **changes):
        request = self.request if request is None else request
        return core.DelegatedWorkloadNodeHealthReadGrant(**{
            "profile": core.DelegatedWorkloadNodeHealthReadGrantProfile.V1,
            "canonicalization": core.NodeControlCanonicalization.JCS_RFC8785_V1,
            "purpose": core.DelegationKeyPurpose.WORKLOAD_NODE_HEALTH_READ,
            "issuer": fixtures.ISSUER, "key_id": self.key.key_id, "audience": fixtures.AUDIENCE,
            "target": request.target, "runtime_id": request.runtime_id, "kind": request.kind,
            "declaration_identity": request.declaration_identity,
            "request_id": request.request_id, "request_digest": request.canonical_digest(),
            "issued_at": 100, "not_before": 100, "expires_at": 200, "jti": "health-jti-a",
            **changes,
        })

    def header(self, grant):
        return {"alg": "EdDSA", "kid": grant.key_id, "typ": TOKEN_TYPE}

    def payload(self, grant):
        return {
            "iss": grant.issuer, "aud": grant.audience, "iat": grant.issued_at,
            "nbf": grant.not_before, "exp": grant.expires_at, "jti": grant.jti,
            PAYLOAD_KEY: grant.descriptor(),
        }

    def token(self, grant=None, *, private=None, header=None, payload=None):
        grant = self.grant() if grant is None else grant
        return fixtures._signed_compact(
            self.private if private is None else private,
            header_bytes=fixtures._json_value(self.header(grant) if header is None else header),
            payload_bytes=fixtures._json_value(self.payload(grant) if payload is None else payload),
        )

    def admit(self, token, *, verifier=None, **changes):
        return (self.verifier() if verifier is None else verifier).admit(token, **{
            "route_kind": self.request.kind, "candidate": None,
            "expected_target": self.target, "expected_runtime_id": self.runtime,
            "expected_declaration": self.declaration, **changes,
        })

    def rejected(self, action):
        with self.assertRaises(verification.WorkloadNodeHealthReadVerificationError) as caught:
            action()
        error = caught.exception
        self.assertEqual(str(error), "workload node-health-read credential was rejected")
        self.assertEqual(vars(error), {})
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)

    def test_real_signed_reads_preserve_request_and_use_one_clock_without_replay(self):
        for kind in core.NodeHealthReadKind:
            request = replace(self.request, kind=kind)
            token = self.token(self.grant(request))
            for _ in range(2):
                admitted = self.admit(token, route_kind=kind)
                self.assertIs(type(admitted), core.NodeHealthReadRequest)
                self.assertEqual(admitted, request)
                self.assertEqual(admitted.canonical_bytes(), request.canonical_bytes())
        self.assertEqual(self.clock_calls, 4)
        self.assertNotIn("Ed25519WorkloadNodeHealthReadVerifier", sdk.__all__)
        self.assertFalse(hasattr(sdk, "Ed25519WorkloadNodeHealthReadVerifier"))

    def test_real_maximum_signed_envelope_and_independent_framing_bounds(self):
        identifier = "a" * 128
        target = core.NodeControlTarget(**{
            name: replace(getattr(self.target, name), value=identifier)
            for name in ("workspace_id", "graph_revision", "node_id", "provider_socket_name")
        })
        declaration = replace(self.declaration, surface=replace(
            self.declaration.surface, provider_socket_name=target.provider_socket_name,
        ))
        request = replace(
            self.request, target=target, runtime_id=replace(self.runtime, value=identifier),
            declaration_identity=declaration.identity(), request_id=identifier,
        )
        grant = self.grant(
            request, issuer="a" * 256, audience="a" * 256, key_id=identifier, jti=identifier,
            issued_at=2**53-301, not_before=2**53-301, expires_at=2**53-1,
        )
        holder = sdk.AtomicWorkloadNodeHealthReadVerifierKeySet(
            self.snapshot(replace(self.key, key_id=identifier)),
        )
        verifier = self.verifier(
            holder=holder, expected_issuer=grant.issuer, expected_audience=grant.audience,
            clock=lambda: grant.expires_at-1,
        )
        token = self.token(grant)
        self.assertEqual(len(grant.canonical_bytes()), 2107)
        self.assertEqual(tuple(map(len, token.split(b"."))), (259, 3831, 86))
        self.assertEqual(len(token), 4178)
        self.assertEqual(self.admit(
            token, verifier=verifier, expected_target=target,
            expected_runtime_id=request.runtime_id, expected_declaration=declaration,
        ), request)

        # Real signatures also admit bounded JSON whitespace at both segment ceilings.
        normal = self.grant()
        padded = fixtures._signed_compact(
            self.private,
            header_bytes=fixtures._json_for_base64url_length(self.header(normal), 512),
            payload_bytes=fixtures._json_for_base64url_length(self.payload(normal), 3968),
        )
        self.assertEqual(self.admit(padded), self.request)
        parts = padded.split(b".")
        header_over = fixtures._signed_compact(
            self.private,
            header_bytes=fixtures._json_for_base64url_length(self.header(normal), 514),
            payload_bytes=fixtures._json_value(self.payload(normal)),
        )
        payload_over = fixtures._signed_compact(
            self.private, header_bytes=fixtures._json_value(self.header(normal)),
            payload_bytes=fixtures._json_for_base64url_length(self.payload(normal), 3970),
        )
        normal_parts = self.token().split(b".")
        signature_over = b".".join((
            normal_parts[0], normal_parts[1], fixtures._b64url(b"s" * 97),
        ))
        aggregate_over = b".".join((parts[0], parts[1], fixtures._b64url(b"s" * 95)))
        self.assertEqual(len(header_over.split(b".")[0]), 514)
        self.assertEqual(len(payload_over.split(b".")[1]), 3970)
        self.assertEqual(len(signature_over.split(b".")[2]), 130)
        self.assertEqual(tuple(map(len, aggregate_over.split(b"."))), (512, 3968, 127))
        self.assertEqual(len(aggregate_over), 4609)
        # First reachable encoded lengths above the caps have canonical framing.
        # Header/payload cases are genuinely signed; signature/aggregate cases
        # must reject before maintained crypto, not merely fail signature size.
        calls = []
        original = jwt.decode
        def record(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)
        with fixtures._replaced_attribute(jwt, "decode", record):
            for index, value in enumerate((header_over, payload_over, signature_over, aggregate_over)):
                with self.subTest(case=index):
                    for segment in value.split(b"."):
                        self.assertEqual(fixtures._b64url(fixtures._b64url_decode(segment)), segment)
                    self.rejected(lambda: self.admit(value))
        self.assertEqual(calls, [])

    def test_closed_framing_and_json_reject_before_signature_admission(self):
        grant = self.grant()
        header, payload = self.header(grant), self.payload(grant)
        token = self.token()
        parts = token.split(b".")
        duplicate_header = fixtures._raw_object(list(header.items()) + [("typ", TOKEN_TYPE)])
        duplicate_target = fixtures._raw_object(
            list(grant.target.descriptor().items()) + [("node_id", "other")],
        )
        duplicate_grant = fixtures.RawJson(fixtures._raw_object(list({
            **grant.descriptor(), "target": fixtures.RawJson(duplicate_target),
        }.items())))
        duplicate_payload = fixtures.RawJson(fixtures._raw_object(list({
            **payload, PAYLOAD_KEY: duplicate_grant,
        }.items())))
        cases = (
            b"", token.decode("ascii"), b"\xff", token + b".",
            b".".join((parts[0] + b"=", parts[1], parts[2])),
            b".".join((parts[0], parts[1], fixtures._noncanonical_tail(parts[2]))),
            fixtures._signed_compact(self.private, header_bytes=duplicate_header,
                                     payload_bytes=fixtures._json_value(payload)),
            self.token(payload=duplicate_payload),
            self.token(payload={**payload, "extra": "private-marker"}),
            self.token(payload={**payload, "iat": True}),
            self.token(payload={**payload, PAYLOAD_KEY: {**grant.descriptor(), "runtime_id": []}}),
            self.token(header={**header, "alg": "HS256"}),
            self.token(header={**header, "typ": fixtures.SURFACE_TOKEN_TYPE}),
        )
        calls = []
        original = jwt.decode
        def record(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)
        with fixtures._replaced_attribute(jwt, "decode", record):
            for index, value in enumerate(cases):
                with self.subTest(case=index):
                    self.rejected(lambda: self.admit(value))
        self.assertEqual(calls, [])
        self.assertEqual(self.clock_calls, 0)

    def test_bad_signature_outer_inner_profile_and_digest_never_admit(self):
        grant = self.grant()
        payload = self.payload(grant)
        cases = [self.token(private=self.other_private)]
        for field, value in (
            ("purpose", core.DelegationKeyPurpose.WORKLOAD_NODE_CONTROL.value),
            ("profile", "workload-node-control-surface-read-grant.v1"),
            ("request_digest", "f" * 64),
        ):
            cases.append(self.token(payload={**payload, PAYLOAD_KEY: {**grant.descriptor(), field: value}}))
        for field, value in (("iat", 101), ("jti", "other-jti"), ("aud", "other-audience")):
            cases.append(self.token(payload={**payload, field: value}))
        for index, token in enumerate(cases):
            with self.subTest(case=index):
                self.rejected(lambda: self.admit(token))
        # Matching public material does not make protected-header and embedded IDs congruent.
        alias_holder = sdk.AtomicWorkloadNodeHealthReadVerifierKeySet(
            self.snapshot(replace(self.key, key_id="alias-key")),
        )
        token = self.token(header={**self.header(grant), "kid": "alias-key"})
        self.rejected(lambda: self.admit(token, verifier=self.verifier(holder=alias_holder)))

    def test_independent_local_context_route_and_bodyless_input_are_required(self):
        token = self.token()
        changes = [
            {"expected_runtime_id": replace(self.runtime, value="other-runtime")},
            {"route_kind": core.NodeHealthReadKind.LIVENESS},
            {"expected_declaration": replace(self.declaration, surface=replace(
                self.declaration.surface, health_reads=(core.NodeHealthReadKind.LIVENESS,),
            ))},
        ]
        for field in ("workspace_id", "graph_revision", "node_id", "provider_socket_name"):
            changes.append({"expected_target": replace(self.target, **{
                field: replace(getattr(self.target, field), value="other"),
            })})
        for change in changes:
            with self.subTest(local=tuple(change)):
                self.rejected(lambda: self.admit(token, **change))
        before = self.clock_calls
        for candidate in (b"", b"{}", "", 0, False, fixtures.ExplodingReprCandidate()):
            self.rejected(lambda: self.admit(token, candidate=candidate))
        for change in (
            {"route_kind": "readiness"}, {"expected_target": object()},
            {"expected_runtime_id": self.target.node_id}, {"expected_declaration": object()},
        ):
            self.rejected(lambda: self.admit(token, **change))
        self.assertEqual(self.clock_calls, before)

    def test_time_is_half_open_and_invalid_clock_or_errors_stay_redacted(self):
        token = self.token()
        self.assertEqual(self.admit(token, verifier=self.verifier(clock=lambda: 100)), self.request)
        for now in (99, 200, -1, 2**53, True, "private-marker"):
            with self.subTest(clock_type=type(now).__name__):
                self.rejected(lambda: self.admit(token, verifier=self.verifier(clock=lambda: now)))
        def bad_clock():
            raise RuntimeError("authorization: Bearer private-marker")
        self.rejected(lambda: self.admit(token, verifier=self.verifier(clock=bad_clock)))
        def interrupted_clock():
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.admit(token, verifier=self.verifier(clock=interrupted_clock))
        for value in (self.verifier(), self.holder, self.snapshot(self.key)):
            for sensitive in (self.key.public_key_pem, self.key.key_id, fixtures.ISSUER, fixtures.AUDIENCE):
                self.assertNotIn(sensitive, repr(value))

    def test_health_and_old_key_holders_and_signed_families_do_not_substitute(self):
        command_set = sdk.WorkloadNodeControlVerifierKeySet(
            core.DelegationKeyPurpose.WORKLOAD_NODE_CONTROL, (self.key,),
        )
        static_set = sdk.WorkloadNodeControlSurfaceReadVerifierKeySet(
            core.DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ, (self.key,),
        )
        command_holder = sdk.AtomicWorkloadNodeControlVerifierKeySet(command_set)
        static_holder = sdk.AtomicWorkloadNodeControlSurfaceReadVerifierKeySet(static_set)
        for holder in (command_holder, static_holder):
            with self.assertRaises(TypeError):
                self.verifier(holder=holder)
        for value in (command_set, static_set):
            with self.assertRaises(TypeError):
                self.holder.replace(value)
        for holder_type in (
            sdk.AtomicWorkloadNodeControlVerifierKeySet,
            sdk.AtomicWorkloadNodeControlSurfaceReadVerifierKeySet,
        ):
            with self.assertRaises(TypeError):
                holder_type(self.snapshot(self.key))
        static_request = fixtures._surface_request()
        static_grant = fixtures._surface_grant(static_request, key_id=self.key.key_id)
        command_request = fixtures._request(core.NodeControlOperation.READ_STATE)
        command_grant = fixtures._grant(command_request, key_id=self.key.key_id)
        self.rejected(lambda: self.admit(fixtures._surface_token(self.private, static_grant)))
        self.rejected(lambda: self.admit(fixtures._token(self.private, command_grant)))
        for verifier_type, holder, arguments, error in (
            (verification.Ed25519WorkloadNodeControlSurfaceReadVerifier, static_holder,
             {"route_kind": static_request.kind}, verification.WorkloadNodeControlSurfaceReadVerificationError),
            (verification.Ed25519WorkloadNodeControlVerifier, command_holder,
             {"route_operation": command_request.operation, "route_variable": command_request.variable_name},
             verification.WorkloadNodeControlVerificationError),
        ):
            old = verifier_type(holder, expected_issuer=fixtures.ISSUER,
                                expected_audience=fixtures.AUDIENCE, clock=lambda: 150)
            with self.assertRaises(error):
                old.admit(self.token(), candidate=None, **arguments)
        for purpose in core.DelegationKeyPurpose:
            if purpose is not core.DelegationKeyPurpose.WORKLOAD_NODE_HEALTH_READ:
                with self.assertRaises(ValueError):
                    sdk.WorkloadNodeHealthReadVerifierKeySet(purpose, (self.key,))
                raw = self.payload(self.grant())
                raw[PAYLOAD_KEY]["purpose"] = purpose.value
                self.rejected(lambda: self.admit(self.token(payload=raw)))

    def test_health_snapshots_are_bounded_unique_and_one_admission_uses_one_snapshot(self):
        maximum = tuple(core.DelegationPublicKey(
            f"health-{index}", core.DelegationKeyAlgorithm.ED25519,
            fixtures._public_pem(ed25519.Ed25519PrivateKey.generate()),
        ) for index in range(16))
        self.assertEqual(len(self.snapshot(*maximum).public_keys), 16)
        ordered = self.snapshot(self.other_key, self.key)
        self.assertEqual(ordered.public_keys, (self.key, self.other_key))
        self.assertIs(self.holder.replace(ordered), ordered)
        self.assertIs(self.holder.snapshot(), ordered)
        for keys in ((), (self.key,) * 17, (self.key, self.key),
                     (self.key, replace(self.other_key, key_id=self.key.key_id)),
                     (self.key, replace(self.key, key_id="same-material"))):
            with self.assertRaises(ValueError):
                self.snapshot(*keys)
        malformed = replace(self.key)
        object.__setattr__(malformed, "fingerprint_sha256", "f" * 64)
        for value in (malformed, object(), fixtures.ExplodingReprCandidate()):
            with self.assertRaises(ValueError):
                self.snapshot(value)
        self.holder.replace(self.snapshot(self.key))
        original = jwt.decode
        calls = []
        def rotate_during_admission(*args, **kwargs):
            calls.append(1)
            self.holder.replace(self.snapshot(self.other_key))
            return original(*args, **kwargs)
        token = self.token()
        with fixtures._replaced_attribute(jwt, "decode", rotate_during_admission):
            self.assertEqual(self.admit(token), self.request)
        self.assertEqual(calls, [1])
        self.assertEqual(self.clock_calls, 1)
        self.rejected(lambda: self.admit(token))
        self.assertEqual(self.admit(self.token(
            self.grant(key_id=self.other_key.key_id), private=self.other_private,
        )), self.request)


if __name__ == "__main__":
    unittest.main()
