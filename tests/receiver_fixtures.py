"""Accepted Core receiver values and ephemeral signed inputs for SDK tests."""
from contextlib import contextmanager
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import ed25519

import control_plane_kit_core as core
from control_plane_kit_core.wrapper_configuration import (
    NodeControlVerificationConfiguration, WORKLOAD_NODE_CONTROL_CONFIGURATION_ENVIRONMENT,
)
from tests import test_verification as signed
from tests import test_fastapi_control_routes as variables


class ReceiverFixture:
    def __init__(self, *, mixed=False, health=True):
        role = core.NodeControlGraphReferenceRole
        ref = core.NodeControlGraphReference
        self.target = core.NodeControlReceiverTarget(
            ref(role.WORKSPACE, "workspace-a"), ref(role.RUNTIME, "runtime-a"),
            ref(role.NODE, "worker"), ref(role.PROVIDER_SOCKET, "control"), "a" * 32)
        self.context = core.NodeControlAuthorityContext("graph-a", "projection-a")
        self.declaration = core.WorkloadNodeControlSurfaceDeclaration(
            core.WorkloadNodeControlSurfaceDescriptor(
                self.target.provider_socket_name,
                (variables._descriptor("routing"),) if mixed else (),
                health_reads=(core.NodeHealthReadKind.LIVENESS, core.NodeHealthReadKind.READINESS) if health else ()),
            core.WorkloadNodeControlSurfaceDeclarationProfile.V2 if health else
            core.WorkloadNodeControlSurfaceDeclarationProfile.V1)
        purposes = [core.DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ]
        if health:
            purposes.append(core.DelegationKeyPurpose.WORKLOAD_NODE_HEALTH_READ)
        if mixed:
            purposes.append(core.DelegationKeyPurpose.WORKLOAD_NODE_CONTROL)
        self.private = {purpose: ed25519.Ed25519PrivateKey.generate() for purpose in purposes}
        self.keys = {purpose: core.DelegationPublicKey(
            "key-" + str(index), core.DelegationKeyAlgorithm.ED25519,
            signed._public_pem(self.private[purpose])) for index, purpose in enumerate(purposes)}
        self.configuration = core.ReceiverNodeControlConfiguration(
            self.target, self.declaration, tuple(NodeControlVerificationConfiguration(
                purpose, signed.ISSUER, (self.keys[purpose],)) for purpose in purposes))
        self.encoded = core.ReceiverNodeControlConfigurationCodec().encode_bytes(self.configuration)

    def health_request(self, *, context=None, **changes):
        return core.ReceiverHealthReadRequest(**{
            "target": self.target, "authority_context": self.context if context is None else context,
            "kind": core.NodeHealthReadKind.READINESS,
            "declaration_identity": self.declaration.identity(), "request_id": "health-a", **changes})

    def surface_request(self, kind):
        return core.ReceiverControlSurfaceReadRequest(
            self.target, self.context, kind, self.declaration.identity(), "surface-a")

    def command_request(self, operation, **changes):
        descriptor = self.declaration.surface.variables[0]
        options = {}
        if operation is core.NodeControlOperation.APPLY_COMMAND:
            codec = descriptor.contract_for(operation).command_codec
            options = dict(command_codec=codec, precondition=core.ControlPlaneTransitionPrecondition(0),
                payload=core.NodeControlPayload(codec, core.ScalarControlState("green")))
        return core.ReceiverNodeControlRequest(**(dict(
            target=self.target, authority_context=self.context, declaration_identity=self.declaration.identity(),
            variable_name=descriptor.variable_name, operation=operation,
            request_id="command-" + operation.value, idempotency_key="key-" + operation.value,
            **options) | changes))

    def grant(self, request, **changes):
        fields = dict(target=request.target, authority_context=request.authority_context,
            declaration_identity=request.declaration_identity, request_id=request.request_id,
            request_digest=request.canonical_digest(), issuer=signed.ISSUER,
            audience=core.receiver_node_control_audience(self.target),
            issued_at=100, not_before=100, expires_at=200, jti="test-jti")
        if type(request) is core.ReceiverHealthReadRequest:
            purpose = core.DelegationKeyPurpose.WORKLOAD_NODE_HEALTH_READ
            factory = core.DelegatedWorkloadReceiverHealthReadGrant
            fields.update(profile=core.DelegatedWorkloadReceiverHealthReadGrantProfile.V2,
                canonicalization=core.NodeControlCanonicalization.JCS_RFC8785_V1,
                purpose=purpose, kind=request.kind)
        elif type(request) is core.ReceiverControlSurfaceReadRequest:
            purpose = core.DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ
            factory = core.DelegatedWorkloadReceiverControlSurfaceReadGrant
            fields.update(profile=core.DelegatedWorkloadReceiverControlSurfaceReadGrantProfile.V2,
                canonicalization=core.NodeControlCanonicalization.JCS_RFC8785_V1,
                purpose=purpose, kind=request.kind)
        else:
            purpose = core.DelegationKeyPurpose.WORKLOAD_NODE_CONTROL
            factory = core.DelegatedWorkloadReceiverNodeControlGrant
            fields.update(profile=core.DelegatedWorkloadReceiverNodeControlGrantProfile.V2,
                variable_name=request.variable_name, operation=request.operation,
                command_codec=request.command_codec, idempotency_key=request.idempotency_key)
        fields.update(key_id=self.keys[purpose].key_id)
        return purpose, factory(**(fields | changes))

    def token(self, request, *, grant_changes=None, document_changes=None, private=None):
        purpose, grant = self.grant(request, **(grant_changes or {}))
        families = {
            core.DelegationKeyPurpose.WORKLOAD_NODE_HEALTH_READ:
                ("CPK-WORKLOAD-NODE-HEALTH-READ+JWT", "workload_node_health_read"),
            core.DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ:
                ("CPK-WORKLOAD-NODE-CONTROL-SURFACE-READ+JWT", "workload_node_control_surface_read"),
            core.DelegationKeyPurpose.WORKLOAD_NODE_CONTROL:
                ("CPK-WORKLOAD-NODE-CONTROL+JWT", "workload_node_control"),
        }
        token_type, field = families[purpose]
        header = dict(alg="EdDSA", kid=grant.key_id, typ=token_type)
        payload = dict(iss=grant.issuer, aud=grant.audience, iat=grant.issued_at,
            nbf=grant.not_before, exp=grant.expires_at, jti=grant.jti)
        payload[field] = grant.descriptor() | (document_changes or {})
        return signed._signed_compact(self.private[purpose] if private is None else private,
            header_bytes=signed._json_value(header), payload_bytes=signed._json_value(payload))

    @contextmanager
    def delivered(self, raw=None):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "receiver.json"
            path.write_bytes(self.encoded if raw is None else raw)
            path.chmod(0o444)
            with patch.dict(os.environ, {WORKLOAD_NODE_CONTROL_CONFIGURATION_ENVIRONMENT: str(path)}):
                yield path
