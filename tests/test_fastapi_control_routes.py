from __future__ import annotations

import asyncio
import base64
from dataclasses import replace
import importlib
import importlib.util
import inspect
import json
from pathlib import Path
from threading import Event, Lock, get_ident
import tomllib
import unittest

import rfc8785
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from control_plane_kit_core import (
    ControlPlaneCommandCodec,
    ControlPlaneResultCodec,
    ControlPlaneStateCodec,
    ControlPlaneTransitionPrecondition,
    ControlPlaneVariableDescriptor,
    ControlPlaneVariableKind,
    ControlPlaneVariableOperationContract,
    DelegatedWorkloadNodeControlGrant,
    DelegatedWorkloadNodeControlSurfaceReadGrant,
    DelegatedWorkloadNodeControlSurfaceReadGrantProfile,
    DelegationKeyAlgorithm,
    DelegationKeyPurpose,
    DelegationPublicKey,
    NodeControlCanonicalization,
    NodeControlCommandRequest,
    NodeControlEvidence,
    NodeControlEvidenceCode,
    NodeControlGraphReference,
    NodeControlGraphReferenceRole,
    NodeControlOperation,
    NodeControlPayload,
    NodeControlReadStateSucceeded,
    NodeControlSurfaceReadKind,
    NodeControlSurfaceReadContractError,
    NodeControlSurfaceReadRequest,
    NodeControlSurfaceReadResultCodec,
    NodeControlTarget,
    NodeControlTransitionSucceeded,
    MAX_NODE_CONTROL_SURFACE_CAPABILITIES_RESULT_BYTES,
    MAX_NODE_CONTROL_SURFACE_STATUS_RESULT_BYTES,
    ScalarControlState,
    WorkloadNodeControlSurfaceDeclaration,
    WorkloadNodeControlSurfaceDescriptor,
)
from control_plane_kit_core.control_routes import NODE_CONTROL_ROUTES
from control_plane_kit_server_sdk import ControlPlaneInvocationContext
from control_plane_kit_server_sdk.verification import (
    Ed25519WorkloadNodeControlSurfaceReadVerifier,
    Ed25519WorkloadNodeControlVerifier,
)
from control_plane_kit_server_sdk.verifier_keys import (
    AtomicWorkloadNodeControlSurfaceReadVerifierKeySet,
    AtomicWorkloadNodeControlVerifierKeySet,
    WorkloadNodeControlSurfaceReadVerifierKeySet,
    WorkloadNodeControlVerifierKeySet,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_NAME = "control_plane_kit_server_sdk.fastapi"
ISSUER = "cpk-server"
AUDIENCE = "workload:router:control"
NOW = 150
SURFACE_TOKEN_TYPE = "CPK-WORKLOAD-NODE-CONTROL-SURFACE-READ+JWT"
SURFACE_PAYLOAD_KEY = "workload_node_control_surface_read"


def _reference(
    role: NodeControlGraphReferenceRole,
    value: str,
) -> NodeControlGraphReference:
    return NodeControlGraphReference(role, value)


def _target(**changes: object) -> NodeControlTarget:
    values: dict[str, object] = {
        "workspace_id": _reference(
            NodeControlGraphReferenceRole.WORKSPACE,
            "workspace-1",
        ),
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


def _descriptor(
    name: str,
    *,
    kind: ControlPlaneVariableKind = ControlPlaneVariableKind.SCALAR,
    description: str | None = None,
) -> ControlPlaneVariableDescriptor:
    state_codecs = {
        ControlPlaneVariableKind.SCALAR: ControlPlaneStateCodec.SCALAR_V1,
        ControlPlaneVariableKind.MAP: ControlPlaneStateCodec.MAP_V1,
        ControlPlaneVariableKind.WEIGHTED_ROUTING: ControlPlaneStateCodec.WEIGHTED_ROUTING_V1,
    }
    command_codecs = {
        ControlPlaneVariableKind.SCALAR: ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
        ControlPlaneVariableKind.MAP: ControlPlaneCommandCodec.REPLACE_MAP_V1,
        ControlPlaneVariableKind.WEIGHTED_ROUTING: ControlPlaneCommandCodec.REPLACE_WEIGHTED_ROUTING_V1,
    }
    return ControlPlaneVariableDescriptor(
        variable_name=_reference(NodeControlGraphReferenceRole.VARIABLE, name),
        kind=kind,
        state_codec=state_codecs[kind],
        operation_contracts=(
            ControlPlaneVariableOperationContract(
                NodeControlOperation.READ_STATE,
                None,
                ControlPlaneResultCodec.STATE_V1,
            ),
            ControlPlaneVariableOperationContract(
                NodeControlOperation.APPLY_COMMAND,
                command_codecs[kind],
                ControlPlaneResultCodec.TRANSITION_V1,
            ),
        ),
        description=description,
    )


def _declaration(*names: str) -> WorkloadNodeControlSurfaceDeclaration:
    return _declaration_from(tuple(_descriptor(name) for name in names))


def _declaration_from(
    descriptors: tuple[ControlPlaneVariableDescriptor, ...],
    *,
    socket: str = "control",
) -> WorkloadNodeControlSurfaceDeclaration:
    return WorkloadNodeControlSurfaceDeclaration(
        WorkloadNodeControlSurfaceDescriptor(
            provider_socket_name=_reference(
                NodeControlGraphReferenceRole.PROVIDER_SOCKET,
                socket,
            ),
            variables=descriptors,
        )
    )


def _maximum_capability_declaration() -> WorkloadNodeControlSurfaceDeclaration:
    description_lengths = [512] * 17 + [430, 1]
    return _declaration_from(
        tuple(
            _descriptor(
                f"variable-{index:03d}",
                description="x" * length,
            )
            for index, length in enumerate(description_lengths)
        )
    )


def _maximum_status_declaration() -> WorkloadNodeControlSurfaceDeclaration:
    return _declaration_from(
        tuple(
            _descriptor(
                f"v{index:03d}" + "x" * 124,
                kind=ControlPlaneVariableKind.MAP,
            )
            for index in range(33)
        ),
        socket="c",
    )


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _b64url(value: bytes) -> bytes:
    return base64.urlsafe_b64encode(value).rstrip(b"=")


def _surface_request(
    declaration: WorkloadNodeControlSurfaceDeclaration,
    kind: NodeControlSurfaceReadKind,
    *,
    target: NodeControlTarget | None = None,
    request_id: str = "surface-read-1",
) -> NodeControlSurfaceReadRequest:
    return NodeControlSurfaceReadRequest(
        target=_target() if target is None else target,
        kind=kind,
        declaration_identity=declaration.identity(),
        request_id=request_id,
    )


def _surface_grant(
    request: NodeControlSurfaceReadRequest,
) -> DelegatedWorkloadNodeControlSurfaceReadGrant:
    return DelegatedWorkloadNodeControlSurfaceReadGrant(
        profile=DelegatedWorkloadNodeControlSurfaceReadGrantProfile.V1,
        canonicalization=NodeControlCanonicalization.JCS_RFC8785_V1,
        purpose=DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
        issuer=ISSUER,
        key_id="surface-key-a",
        audience=AUDIENCE,
        target=request.target,
        kind=request.kind,
        declaration_identity=request.declaration_identity,
        request_id=request.request_id,
        request_digest=request.canonical_digest(),
        issued_at=100,
        not_before=100,
        expires_at=200,
        jti="surface-grant-1",
    )


def _surface_token(
    private_key: ed25519.Ed25519PrivateKey,
    request: NodeControlSurfaceReadRequest,
) -> bytes:
    grant = _surface_grant(request)
    header = {
        "alg": "EdDSA",
        "kid": grant.key_id,
        "typ": SURFACE_TOKEN_TYPE,
    }
    payload = {
        "iss": grant.issuer,
        "aud": grant.audience,
        "iat": grant.issued_at,
        "nbf": grant.not_before,
        "exp": grant.expires_at,
        "jti": grant.jti,
        SURFACE_PAYLOAD_KEY: grant.descriptor(),
    }
    signing_input = _b64url(_json_bytes(header)) + b"." + _b64url(
        _json_bytes(payload)
    )
    return signing_input + b"." + _b64url(private_key.sign(signing_input))


def _command_request(
    operation: NodeControlOperation,
    *,
    target: NodeControlTarget | None = None,
    variable: str = "routing",
    request_id: str = "command-request-1",
    idempotency_key: str = "command-key-1",
) -> NodeControlCommandRequest:
    values: dict[str, object] = {
        "target": _target() if target is None else target,
        "variable_name": _reference(
            NodeControlGraphReferenceRole.VARIABLE,
            variable,
        ),
        "operation": operation,
        "request_id": request_id,
        "idempotency_key": idempotency_key,
    }
    if operation is NodeControlOperation.APPLY_COMMAND:
        values.update(
            command_codec=ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
            precondition=ControlPlaneTransitionPrecondition(1),
            payload=NodeControlPayload(
                ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
                ScalarControlState("blue"),
            ),
        )
    return NodeControlCommandRequest(**values)


def _command_token(
    private_key: ed25519.Ed25519PrivateKey,
    request: NodeControlCommandRequest,
) -> bytes:
    grant = DelegatedWorkloadNodeControlGrant(
        issuer=ISSUER,
        key_id="workload-key-a",
        audience=AUDIENCE,
        target=request.target,
        variable_name=request.variable_name,
        operation=request.operation,
        command_codec=request.command_codec,
        request_id=request.request_id,
        idempotency_key=request.idempotency_key,
        request_digest=request.canonical_digest(),
        issued_at=100,
        not_before=100,
        expires_at=200,
        jti="command-grant-1",
    )
    header = {
        "alg": "EdDSA",
        "kid": grant.key_id,
        "typ": "CPK-WORKLOAD-NODE-CONTROL+JWT",
    }
    payload = {
        "iss": grant.issuer,
        "aud": grant.audience,
        "iat": grant.issued_at,
        "nbf": grant.not_before,
        "exp": grant.expires_at,
        "jti": grant.jti,
        "workload_node_control": grant.descriptor(),
    }
    signing_input = _b64url(_json_bytes(header)) + b"." + _b64url(
        _json_bytes(payload)
    )
    return signing_input + b"." + _b64url(private_key.sign(signing_input))


def _public_pem(private_key: ed25519.Ed25519PrivateKey) -> str:
    return private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


class RecordingVariable:
    def __init__(
        self,
        name: str | None = None,
        *,
        descriptor: ControlPlaneVariableDescriptor | None = None,
        apply_gate: tuple[Event, Event] | None = None,
    ) -> None:
        self._descriptor = _descriptor(name or "routing") if descriptor is None else descriptor
        self.apply_gate = apply_gate
        self.descriptor_calls = 0
        self.read_calls = 0
        self.apply_calls = 0

    def descriptor(self) -> ControlPlaneVariableDescriptor:
        self.descriptor_calls += 1
        return self._descriptor

    def read(self, context: ControlPlaneInvocationContext) -> object:
        self.read_calls += 1
        return NodeControlReadStateSucceeded(
            context.request.request_id,
            ControlPlaneStateCodec.SCALAR_V1,
            1,
            ScalarControlState("green"),
        )

    def apply(self, command: object, context: ControlPlaneInvocationContext) -> object:
        self.apply_calls += 1
        if self.apply_gate is not None:
            entered, release = self.apply_gate
            entered.set()
            release.wait(3)
        return NodeControlTransitionSucceeded(
            context.request.request_id,
            2,
            NodeControlEvidence(NodeControlEvidenceCode.APPLIED),
        )


class SensitiveDescriptorVariable:
    def descriptor(self) -> object:
        raise RuntimeError("authorization: Bearer descriptor-secret")

    def read(self, _context: object) -> object:
        raise AssertionError

    def apply(self, _command: object, _context: object) -> object:
        raise AssertionError


class RecordingClock:
    def __init__(self, value: int = NOW) -> None:
        self.value = value
        self.calls = 0
        self.thread_ids: list[int] = []
        self.second_call = Event()
        self._lock = Lock()

    def __call__(self) -> int:
        with self._lock:
            self.calls += 1
            self.thread_ids.append(get_ident())
            if self.calls >= 2:
                self.second_call.set()
        return self.value


class FastApiControlRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.command_private = ed25519.Ed25519PrivateKey.generate()
        cls.surface_private = ed25519.Ed25519PrivateKey.generate()
        command_public = DelegationPublicKey(
            "workload-key-a",
            DelegationKeyAlgorithm.ED25519,
            _public_pem(cls.command_private),
        )
        surface_public = DelegationPublicKey(
            "surface-key-a",
            DelegationKeyAlgorithm.ED25519,
            _public_pem(cls.surface_private),
        )
        cls.command_holder = AtomicWorkloadNodeControlVerifierKeySet(
            WorkloadNodeControlVerifierKeySet(
                DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
                (command_public,),
            )
        )
        cls.surface_holder = AtomicWorkloadNodeControlSurfaceReadVerifierKeySet(
            WorkloadNodeControlSurfaceReadVerifierKeySet(
                DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
                (surface_public,),
            )
        )

    def _module(self):
        specification = importlib.util.find_spec(MODULE_NAME)
        self.assertIsNotNone(
            specification,
            "missing public optional FastAPI control-route adapter",
        )
        return importlib.import_module(MODULE_NAME)

    def _command_verifier(self, clock=None) -> Ed25519WorkloadNodeControlVerifier:
        return Ed25519WorkloadNodeControlVerifier(
            self.command_holder,
            expected_issuer=ISSUER,
            expected_audience=AUDIENCE,
            clock=(lambda: NOW) if clock is None else clock,
        )

    def _surface_verifier(
        self,
        clock=None,
    ) -> Ed25519WorkloadNodeControlSurfaceReadVerifier:
        return Ed25519WorkloadNodeControlSurfaceReadVerifier(
            self.surface_holder,
            expected_issuer=ISSUER,
            expected_audience=AUDIENCE,
            clock=(lambda: NOW) if clock is None else clock,
        )

    def _app(self):
        fastapi = importlib.import_module("fastapi")
        app = fastapi.FastAPI()

        @app.get("/ordinary")
        async def ordinary() -> dict[str, str]:
            return {"message": "ordinary"}

        return app

    def _install(
        self,
        app,
        *,
        declaration: WorkloadNodeControlSurfaceDeclaration,
        variables: tuple[object, ...],
        target: NodeControlTarget | None = None,
        command_verifier: object | None = None,
        surface_verifier: object | None = None,
    ) -> None:
        self._module().install_cpk_control_routes(
            app,
            target=_target() if target is None else target,
            declaration=declaration,
            variables=variables,
            command_verifier=(
                self._command_verifier()
                if command_verifier is None
                else command_verifier
            ),
            surface_read_verifier=(
                self._surface_verifier()
                if surface_verifier is None
                else surface_verifier
            ),
        )

    @staticmethod
    def _authorization(token: bytes) -> tuple[bytes, bytes]:
        return b"authorization", b"Bearer " + token

    async def _asgi_request(
        self,
        app,
        method: str,
        path: str,
        *,
        headers: list[tuple[bytes, bytes]] | None = None,
        chunks: tuple[bytes, ...] = (b"",),
        query_string: bytes = b"",
    ) -> tuple[int, bytes]:
        messages = [
            {
                "type": "http.request",
                "body": chunk,
                "more_body": index < len(chunks) - 1,
            }
            for index, chunk in enumerate(chunks)
        ]
        sent: list[dict[str, object]] = []

        async def receive() -> dict[str, object]:
            if messages:
                return messages.pop(0)
            return {"type": "http.disconnect"}

        async def send(message: dict[str, object]) -> None:
            sent.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": query_string,
            "headers": [] if headers is None else headers,
            "client": ("test", 123),
            "server": ("test", 80),
            "root_path": "",
        }
        await app(scope, receive, send)
        status = next(
            int(message["status"])
            for message in sent
            if message["type"] == "http.response.start"
        )
        body = b"".join(
            message.get("body", b"")
            for message in sent
            if message["type"] == "http.response.body"
        )
        return status, body

    def _surface_call(
        self,
        app,
        declaration: WorkloadNodeControlSurfaceDeclaration,
        kind: NodeControlSurfaceReadKind,
        **request_changes: object,
    ) -> tuple[NodeControlSurfaceReadRequest, int, bytes]:
        request = _surface_request(declaration, kind, **request_changes)
        token = _surface_token(self.surface_private, request)
        path = (
            "/__control/capabilities"
            if kind is NodeControlSurfaceReadKind.CAPABILITIES
            else "/__control/status"
        )
        status, body = asyncio.run(
            self._asgi_request(
                app,
                "GET",
                path,
                headers=[self._authorization(token)],
            )
        )
        return request, status, body

    async def _command_call(
        self,
        app,
        request: NodeControlCommandRequest,
    ) -> tuple[int, bytes]:
        if request.operation is NodeControlOperation.READ_STATE:
            method = "GET"
            path = f"/__control/variables/{request.variable_name.value}"
            chunks = (b"",)
        else:
            method = "POST"
            path = (
                f"/__control/variables/{request.variable_name.value}/commands"
            )
            chunks = (_json_bytes(request.descriptor()),)
        return await self._asgi_request(
            app,
            method,
            path,
            headers=[
                self._authorization(
                    _command_token(self.command_private, request)
                )
            ],
            chunks=chunks,
        )

    def test_public_optional_module_signature_and_exact_dependency_truth(self) -> None:
        module = self._module()
        self.assertEqual(module.__all__, ["install_cpk_control_routes"])
        function = module.install_cpk_control_routes
        self.assertEqual(
            tuple(inspect.signature(function).parameters),
            (
                "app",
                "target",
                "declaration",
                "variables",
                "command_verifier",
                "surface_read_verifier",
            ),
        )
        root = importlib.import_module("control_plane_kit_server_sdk")
        self.assertNotIn("install_cpk_control_routes", root.__all__)
        self.assertFalse(hasattr(root, "install_cpk_control_routes"))

        metadata = tomllib.loads(
            (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            metadata["project"]["optional-dependencies"]["fastapi"],
            [
                "PyJWT==2.13.0",
                "cryptography==50.0.0",
                "fastapi==0.141.1",
                "starlette==1.6.0",
            ],
        )

    def test_installation_is_one_canonical_hidden_route_publication(self) -> None:
        app = self._app()
        prior_routes = app.router.routes
        prior_identities = tuple(map(id, prior_routes))
        prior_route_states = tuple(
            (route, dict(vars(route))) for route in prior_routes
        )
        cached_schema = app.openapi()
        ordinary_schema = json.loads(json.dumps(cached_schema["paths"]["/ordinary"]))
        app_state = dict(vars(app))
        router_state = {
            key: value
            for key, value in vars(app.router).items()
            if key != "routes"
        }
        starlette_state = dict(app.state._state)
        variable = RecordingVariable("routing")

        self._install(app, declaration=_declaration("routing"), variables=(variable,))

        self.assertIsNot(app.router.routes, prior_routes)
        self.assertEqual(
            tuple(map(id, app.router.routes[: len(prior_routes)])),
            prior_identities,
        )
        installed = app.router.routes[len(prior_routes) :]
        self.assertEqual(len(installed), 4)
        self.assertEqual(
            tuple((route.name, next(iter(route.methods)), route.path) for route in installed),
            tuple(
                (route.name, route.method.value, route.path)
                for route in NODE_CONTROL_ROUTES.routes
            ),
        )
        self.assertTrue(all(route.include_in_schema is False for route in installed))
        self.assertIs(app.openapi(), cached_schema)
        self.assertEqual(app.openapi()["paths"]["/ordinary"], ordinary_schema)
        self.assertTrue(
            all(not path.startswith("/__control") for path in app.openapi()["paths"])
        )
        self.assertEqual(variable.descriptor_calls, 1)
        for route, state in prior_route_states:
            self.assertEqual(set(vars(route)), set(state))
            self.assertTrue(
                all(vars(route)[key] is value for key, value in state.items())
            )
        self.assertEqual(set(vars(app)), set(app_state))
        self.assertTrue(
            all(vars(app)[key] is value for key, value in app_state.items())
        )
        self.assertEqual(set(vars(app.router)) - {"routes"}, set(router_state))
        self.assertTrue(
            all(
                vars(app.router)[key] is value
                for key, value in router_state.items()
            )
        )
        self.assertEqual(app.state._state, starlette_state)

    def test_fresh_openapi_never_exposes_control_routes(self) -> None:
        app = self._app()
        self.assertIsNone(app.openapi_schema)
        self._install(
            app,
            declaration=_declaration("routing"),
            variables=(RecordingVariable("routing"),),
        )
        schema = app.openapi()
        self.assertIn("/ordinary", schema["paths"])
        self.assertTrue(
            all(not path.startswith("/__control") for path in schema["paths"])
        )

    def test_public_installer_executes_read_apply_and_one_replay_waiter(self) -> None:
        declaration = _declaration("routing")
        read_variable = RecordingVariable("routing")
        read_app = self._app()
        self._install(
            read_app,
            declaration=declaration,
            variables=(read_variable,),
        )
        read = _command_request(NodeControlOperation.READ_STATE)
        read_status, read_body = asyncio.run(self._command_call(read_app, read))
        self.assertEqual(read_status, 200)
        self.assertEqual(
            json.loads(read_body),
            NodeControlResultCodec(_descriptor("routing")).encode(
                NodeControlReadStateSucceeded(
                    read.request_id,
                    ControlPlaneStateCodec.SCALAR_V1,
                    1,
                    ScalarControlState("green"),
                )
            ),
        )
        self.assertEqual(read_variable.read_calls, 1)

        entered = Event()
        release = Event()
        command_clock = RecordingClock()
        variable = RecordingVariable(
            "routing",
            apply_gate=(entered, release),
        )
        app = self._app()
        self._install(
            app,
            declaration=declaration,
            variables=(variable,),
            command_verifier=self._command_verifier(command_clock),
        )

        apply = _command_request(NodeControlOperation.APPLY_COMMAND)

        async def concurrent_apply() -> tuple[tuple[int, bytes], tuple[int, bytes]]:
            owner = asyncio.create_task(self._command_call(app, apply))
            entered_ok = await asyncio.to_thread(entered.wait, 2)
            self.assertTrue(entered_ok)
            waiter = asyncio.create_task(self._command_call(app, apply))
            second_admitted = await asyncio.to_thread(
                command_clock.second_call.wait,
                2,
            )
            self.assertTrue(second_admitted)
            self.assertFalse(owner.done())
            self.assertFalse(waiter.done())
            self.assertEqual(variable.apply_calls, 1)
            heartbeat = asyncio.Event()
            asyncio.get_running_loop().call_soon(heartbeat.set)
            await asyncio.wait_for(heartbeat.wait(), 1)
            release.set()
            return await asyncio.gather(owner, waiter)

        owner_result, waiter_result = asyncio.run(concurrent_apply())
        self.assertEqual(owner_result, waiter_result)
        self.assertEqual(owner_result[0], 200)
        self.assertEqual(
            json.loads(owner_result[1]),
            NodeControlResultCodec(_descriptor("routing")).encode(
                NodeControlTransitionSucceeded(
                    apply.request_id,
                    2,
                    NodeControlEvidence(NodeControlEvidenceCode.APPLIED),
                )
            ),
        )
        self.assertEqual((variable.read_calls, variable.apply_calls), (0, 1))

        foreign = _command_request(
            NodeControlOperation.READ_STATE,
            target=replace(
                _target(),
                node_id=_reference(NodeControlGraphReferenceRole.NODE, "other"),
            ),
            variable="missing",
            request_id="foreign-command",
        )
        foreign_status, foreign_body = asyncio.run(
            self._command_call(app, foreign)
        )
        self.assertEqual(foreign_status, 403)
        self.assertEqual(
            json.loads(foreign_body),
            {"code": "node-control.target-rejected"},
        )

    def test_two_apps_do_not_share_command_registry_or_replay(self) -> None:
        declaration = _declaration("routing")
        first = self._app()
        second = self._app()
        first_variable = RecordingVariable("routing")
        second_variable = RecordingVariable("routing")
        self._install(first, declaration=declaration, variables=(first_variable,))
        self._install(second, declaration=declaration, variables=(second_variable,))
        request = _command_request(NodeControlOperation.APPLY_COMMAND)

        first_result = asyncio.run(self._command_call(first, request))
        second_result = asyncio.run(self._command_call(second, request))

        self.assertEqual(first_result, second_result)
        self.assertEqual(first_result[0], 200)
        self.assertEqual((first_variable.apply_calls, second_variable.apply_calls), (1, 1))

    def test_capabilities_and_status_are_exact_stateless_core_results(self) -> None:
        declaration = _declaration("alpha", "beta")
        alpha = RecordingVariable("alpha")
        app = self._app()
        self._install(app, declaration=declaration, variables=(alpha,))

        capability_request, capability_status, capability_body = self._surface_call(
            app,
            declaration,
            NodeControlSurfaceReadKind.CAPABILITIES,
        )
        capability_codec = NodeControlSurfaceReadResultCodec(
            capability_request,
            declaration,
        )
        self.assertEqual(capability_status, 200)
        self.assertEqual(
            capability_body,
            capability_codec.capabilities_result().canonical_bytes(),
        )

        status_request, status_status, status_body = self._surface_call(
            app,
            declaration,
            NodeControlSurfaceReadKind.STATUS,
            request_id="surface-status-1",
        )
        status_codec = NodeControlSurfaceReadResultCodec(status_request, declaration)
        self.assertEqual(status_status, 200)
        self.assertEqual(
            status_body,
            status_codec.status_result(
                (_reference(NodeControlGraphReferenceRole.VARIABLE, "alpha"),)
            ).canonical_bytes(),
        )

        repeated = self._surface_call(
            app,
            declaration,
            NodeControlSurfaceReadKind.STATUS,
            request_id="surface-status-1",
        )
        self.assertEqual(repeated[1:], (status_status, status_body))
        self.assertEqual(alpha.descriptor_calls, 1)
        self.assertEqual((alpha.read_calls, alpha.apply_calls), (0, 0))

    def test_status_is_permutation_invariant_and_canonical(self) -> None:
        declaration = _declaration("alpha", "beta", "gamma")
        bodies: list[bytes] = []
        variables_by_app: list[tuple[RecordingVariable, RecordingVariable]] = []
        for names in (("gamma", "alpha"), ("alpha", "gamma")):
            app = self._app()
            variables = tuple(RecordingVariable(name) for name in names)
            variables_by_app.append(variables)
            self._install(app, declaration=declaration, variables=variables)
            _, status, body = self._surface_call(
                app,
                declaration,
                NodeControlSurfaceReadKind.STATUS,
            )
            self.assertEqual(status, 200)
            bodies.append(body)
        self.assertEqual(bodies[0], bodies[1])
        self.assertEqual(
            json.loads(bodies[0])["installed_variable_names"],
            ["alpha", "gamma"],
        )
        self.assertTrue(
            all(
                variable.descriptor_calls == 1
                for variables in variables_by_app
                for variable in variables
            )
        )

    def test_empty_partial_and_complete_registry_coverage(self) -> None:
        declaration = _declaration("alpha", "beta")
        for names, expected in (
            ((), "none"),
            (("beta",), "partial"),
            (("alpha", "beta"), "complete"),
        ):
            with self.subTest(names=names):
                app = self._app()
                self._install(
                    app,
                    declaration=declaration,
                    variables=tuple(RecordingVariable(name) for name in names),
                )
                _, status, body = self._surface_call(
                    app,
                    declaration,
                    NodeControlSurfaceReadKind.STATUS,
                )
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["registry_coverage"], expected)

    def test_maximal_surface_results_publish_and_pinned_core_rejects_plus_one(self) -> None:
        capability_declaration = _maximum_capability_declaration()
        capability_app = self._app()
        self._install(
            capability_app,
            declaration=capability_declaration,
            variables=(),
        )
        capability_request, status, capability_body = self._surface_call(
            capability_app,
            capability_declaration,
            NodeControlSurfaceReadKind.CAPABILITIES,
            request_id="r" * 128,
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            len(capability_body),
            MAX_NODE_CONTROL_SURFACE_CAPABILITIES_RESULT_BYTES,
        )

        status_declaration = _maximum_status_declaration()
        status_target = replace(
            _target(),
            provider_socket_name=_reference(
                NodeControlGraphReferenceRole.PROVIDER_SOCKET,
                "c",
            ),
        )
        status_variables = tuple(
            RecordingVariable(descriptor=descriptor)
            for descriptor in status_declaration.surface.variables
        )
        status_app = self._app()
        self._install(
            status_app,
            target=status_target,
            declaration=status_declaration,
            variables=status_variables,
        )
        status_request, status, status_body = self._surface_call(
            status_app,
            status_declaration,
            NodeControlSurfaceReadKind.STATUS,
            target=status_target,
            request_id="r" * 128,
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            len(status_body),
            MAX_NODE_CONTROL_SURFACE_STATUS_RESULT_BYTES,
        )

        for request, declaration, body, maximum in (
            (
                capability_request,
                capability_declaration,
                capability_body,
                MAX_NODE_CONTROL_SURFACE_CAPABILITIES_RESULT_BYTES,
            ),
            (
                status_request,
                status_declaration,
                status_body,
                MAX_NODE_CONTROL_SURFACE_STATUS_RESULT_BYTES,
            ),
        ):
            codec = NodeControlSurfaceReadResultCodec(request, declaration)
            candidate = {**json.loads(body), "unknown": ""}
            padding = maximum + 1 - len(rfc8785.dumps(candidate))
            self.assertGreaterEqual(padding, 0)
            candidate["unknown"] = "x" * padding
            self.assertEqual(len(rfc8785.dumps(candidate)), maximum + 1)
            with self.assertRaisesRegex(
                NodeControlSurfaceReadContractError,
                "aggregate exceeds.*bound",
            ):
                codec.decode(candidate)

    def test_surface_transport_rejects_before_admission_or_discovery(self) -> None:
        declaration = _declaration("routing")
        variable = RecordingVariable("routing")
        clock = RecordingClock()
        app = self._app()
        self._install(
            app,
            declaration=declaration,
            variables=(variable,),
            surface_verifier=self._surface_verifier(clock),
        )
        request = _surface_request(
            declaration,
            NodeControlSurfaceReadKind.CAPABILITIES,
        )
        authorization = self._authorization(
            _surface_token(self.surface_private, request)
        )
        cases = (
            ({"chunks": (b"body-secret",)}, 400, "request-invalid"),
            ({"chunks": (b"", b"late-secret")}, 400, "request-invalid"),
            ({"query_string": b"query-secret=1"}, 400, "request-invalid"),
            (
                {"query_string": b"query-secret" + b"x" * 1_025},
                413,
                "request-too-large",
            ),
            (
                {"chunks": (b"body-secret" + b"x" * 16_385,)},
                413,
                "request-too-large",
            ),
            (
                {"headers": [authorization, authorization]},
                401,
                "credential-rejected",
            ),
            (
                {"headers": [(b"header-secret", b"y" * 32_769)]},
                413,
                "request-too-large",
            ),
        )
        for changes, expected, code in cases:
            with self.subTest(changes=tuple(changes)):
                options = {"headers": [authorization], **changes}
                status, body = asyncio.run(
                    self._asgi_request(
                        app,
                        "GET",
                        "/__control/capabilities",
                        **options,
                    )
                )
                self.assertEqual(status, expected)
                self.assertEqual(
                    body,
                    _json_bytes({"code": f"node-control.{code}"}),
                )
                self.assertLessEqual(len(body), 128)
                for forbidden in (
                    b"body-secret",
                    b"late-secret",
                    b"query-secret",
                    b"header-secret",
                    b"Bearer",
                    b"Traceback",
                ):
                    self.assertNotIn(forbidden, body)
        self.assertEqual(clock.calls, 0)
        self.assertEqual(variable.descriptor_calls, 1)
        self.assertEqual((variable.read_calls, variable.apply_calls), (0, 0))

    def test_surface_admission_precedes_exact_locality_and_disclosure(self) -> None:
        declaration = _declaration("routing")
        substitutions = (
            replace(_target(), workspace_id=_reference(NodeControlGraphReferenceRole.WORKSPACE, "workspace-2")),
            replace(_target(), graph_revision=_reference(NodeControlGraphReferenceRole.GRAPH_REVISION, "revision-8")),
            replace(_target(), node_id=_reference(NodeControlGraphReferenceRole.NODE, "other")),
            replace(_target(), provider_socket_name=_reference(NodeControlGraphReferenceRole.PROVIDER_SOCKET, "other-control")),
        )
        for substituted in substitutions:
            with self.subTest(target=substituted.descriptor()):
                variable = RecordingVariable("routing")
                app = self._app()
                self._install(app, declaration=declaration, variables=(variable,))
                _, status, body = self._surface_call(
                    app,
                    declaration,
                    NodeControlSurfaceReadKind.STATUS,
                    target=substituted,
                )
                self.assertEqual(status, 403)
                self.assertEqual(
                    json.loads(body),
                    {"code": "node-control.target-rejected"},
                )
                self.assertEqual(variable.descriptor_calls, 1)
                self.assertEqual((variable.read_calls, variable.apply_calls), (0, 0))

        variable = RecordingVariable("routing")
        app = self._app()
        self._install(app, declaration=declaration, variables=(variable,))
        alternate = _declaration("other")
        substituted_request = replace(
            _surface_request(
                declaration,
                NodeControlSurfaceReadKind.STATUS,
                request_id="alternate-declaration",
            ),
            declaration_identity=alternate.identity(),
        )
        status, body = asyncio.run(
            self._asgi_request(
                app,
                "GET",
                "/__control/status",
                headers=[
                    self._authorization(
                        _surface_token(self.surface_private, substituted_request)
                    )
                ],
            )
        )
        self.assertEqual(status, 403)
        self.assertEqual(
            json.loads(body),
            {"code": "node-control.target-rejected"},
        )
        self.assertEqual((variable.read_calls, variable.apply_calls), (0, 0))

        variable = RecordingVariable("routing")
        app = self._app()
        self._install(app, declaration=declaration, variables=(variable,))
        status, body = asyncio.run(
            self._asgi_request(app, "GET", "/__control/status", headers=[])
        )
        self.assertEqual(status, 401)
        self.assertEqual(
            json.loads(body),
            {"code": "node-control.credential-rejected"},
        )
        self.assertEqual((variable.read_calls, variable.apply_calls), (0, 0))

    def test_surface_verification_and_results_run_off_the_event_loop(self) -> None:
        declaration = _declaration("routing")
        variable = RecordingVariable("routing")
        clock = RecordingClock()
        app = self._app()
        self._install(
            app,
            declaration=declaration,
            variables=(variable,),
            surface_verifier=self._surface_verifier(clock),
        )
        request = _surface_request(
            declaration,
            NodeControlSurfaceReadKind.CAPABILITIES,
        )
        caller_thread = get_ident()
        status, _ = asyncio.run(
            self._asgi_request(
                app,
                "GET",
                "/__control/capabilities",
                headers=[
                    self._authorization(_surface_token(self.surface_private, request))
                ],
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual(clock.calls, 1)
        self.assertTrue(all(thread_id != caller_thread for thread_id in clock.thread_ids))

    def test_invalid_installation_is_exactly_before_app_mutation(self) -> None:
        fastapi = importlib.import_module("fastapi")
        valid_declaration = _declaration("routing")
        cases = (
            (object(), valid_declaration, (RecordingVariable("routing"),), self._command_verifier(), self._surface_verifier()),
            (self._app(), valid_declaration, [RecordingVariable("routing")], self._command_verifier(), self._surface_verifier()),
            (self._app(), valid_declaration, (RecordingVariable("other"),), self._command_verifier(), self._surface_verifier()),
            (self._app(), valid_declaration, (RecordingVariable("routing"), RecordingVariable("routing")), self._command_verifier(), self._surface_verifier()),
            (self._app(), valid_declaration, (RecordingVariable("routing"),), object(), self._surface_verifier()),
            (self._app(), valid_declaration, (RecordingVariable("routing"),), self._command_verifier(), object()),
            (
                self._app(),
                valid_declaration,
                (RecordingVariable("routing"),),
                self._command_verifier(),
                self._surface_verifier(),
            ),
        )
        for index, (app, declaration, variables, command, surface) in enumerate(cases):
            with self.subTest(index=index):
                if type(app) is fastapi.FastAPI and index == len(cases) - 1:
                    target = replace(
                        _target(),
                        provider_socket_name=_reference(
                            NodeControlGraphReferenceRole.PROVIDER_SOCKET,
                            "other-control",
                        ),
                    )
                else:
                    target = _target()
                prior = app.router.routes if type(app) is fastapi.FastAPI else None
                prior_ids = tuple(map(id, prior)) if prior is not None else ()
                with self.assertRaises(ValueError):
                    self._module().install_cpk_control_routes(
                        app,
                        target=target,
                        declaration=declaration,
                        variables=variables,
                        command_verifier=command,
                        surface_read_verifier=surface,
                    )
                if prior is not None:
                    self.assertIs(app.router.routes, prior)
                    self.assertEqual(tuple(map(id, prior)), prior_ids)

    def test_installation_failures_are_fixed_cause_free_and_state_preserving(self) -> None:
        app = self._app()
        cached_schema = app.openapi()
        prior_routes = app.router.routes
        prior_ids = tuple(map(id, prior_routes))
        prior_route_states = tuple(
            (route, dict(vars(route))) for route in prior_routes
        )
        app_state = dict(vars(app))
        router_state = dict(vars(app.router))
        state_values = dict(app.state._state)

        with self.assertRaises(ValueError) as raised:
            self._install(
                app,
                declaration=_declaration("routing"),
                variables=(SensitiveDescriptorVariable(),),
            )

        rendered = f"{raised.exception!s} {raised.exception!r}"
        self.assertEqual(
            str(raised.exception),
            "FastAPI control route installation is invalid",
        )
        self.assertLessEqual(len(str(raised.exception).encode("utf-8")), 128)
        self.assertNotIn("authorization", rendered)
        self.assertNotIn("descriptor-secret", rendered)
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        self.assertIs(app.router.routes, prior_routes)
        self.assertEqual(tuple(map(id, prior_routes)), prior_ids)
        for route, state in prior_route_states:
            self.assertEqual(set(vars(route)), set(state))
            self.assertTrue(
                all(vars(route)[key] is value for key, value in state.items())
            )
        self.assertIs(app.openapi(), cached_schema)
        self.assertEqual(set(vars(app)), set(app_state))
        self.assertTrue(
            all(vars(app)[key] is value for key, value in app_state.items())
        )
        self.assertEqual(set(vars(app.router)), set(router_state))
        self.assertTrue(
            all(
                vars(app.router)[key] is value
                for key, value in router_state.items()
            )
        )
        self.assertEqual(app.state._state, state_values)

    def test_route_collision_classifier_is_closed_and_fail_closed(self) -> None:
        fastapi = importlib.import_module("fastapi")
        starlette_routing = importlib.import_module("starlette.routing")

        async def endpoint(_request):
            return importlib.import_module("starlette.responses").PlainTextResponse("ok")

        async def asgi_app(_scope, _receive, _send):
            return None

        class CustomRoute(starlette_routing.BaseRoute):
            def matches(self, _scope):
                return starlette_routing.Match.NONE, {}

            def url_path_for(self, _name, **_path_params):
                raise starlette_routing.NoMatchFound

            async def handle(self, _scope, _receive, _send):
                return None

        class RouteSubclass(starlette_routing.Route):
            pass

        builders = (
            lambda app: app.add_api_route("/__control", endpoint, methods=["DELETE"]),
            lambda app: app.add_api_route("/__control/x", endpoint, methods=["PUT"]),
            lambda app: app.add_api_route("/{prefix}/x", endpoint, methods=["GET"]),
            lambda app: app.add_api_route("/{prefix:path}", endpoint, methods=["POST"]),
            lambda app: app.add_api_route("/{value:int}/x", endpoint, methods=["GET"]),
            lambda app: app.add_api_route("/{value}-embedded/x", endpoint, methods=["GET"]),
            lambda app: app.add_api_websocket_route("/__control/socket", endpoint),
            lambda app: app.router.routes.append(
                starlette_routing.Route(
                    "/__control/starlette",
                    endpoint,
                    methods=["PATCH"],
                )
            ),
            lambda app: app.router.routes.append(
                starlette_routing.WebSocketRoute(
                    "/__control/starlette-socket",
                    endpoint,
                )
            ),
            lambda app: app.router.routes.append(starlette_routing.Mount("/", app=asgi_app)),
            lambda app: app.router.routes.append(starlette_routing.Mount("/__control", app=asgi_app)),
            lambda app: app.router.routes.append(starlette_routing.Mount("/{tenant}", app=asgi_app)),
            lambda app: app.router.routes.append(starlette_routing.Host("example.test", app=asgi_app)),
            lambda app: app.router.routes.append(CustomRoute()),
            lambda app: app.router.routes.append(
                RouteSubclass("/ordinary-subclass", endpoint)
            ),
        )
        for index, build in enumerate(builders):
            with self.subTest(index=index):
                app = fastapi.FastAPI()
                build(app)
                prior = app.router.routes
                prior_ids = tuple(map(id, prior))
                with self.assertRaisesRegex(ValueError, "collides"):
                    self._install(
                        app,
                        declaration=_declaration("routing"),
                        variables=(RecordingVariable("routing"),),
                    )
                self.assertIs(app.router.routes, prior)
                self.assertEqual(tuple(map(id, prior)), prior_ids)

        for path in ("/", "/__controlish", "/ordinary/{path:path}"):
            with self.subTest(disjoint=path):
                app = fastapi.FastAPI()
                app.add_api_route(path, endpoint, methods=["GET"])
                self._install(
                    app,
                    declaration=_declaration("routing"),
                    variables=(RecordingVariable("routing"),),
                )
        app = fastapi.FastAPI()
        nested = fastapi.FastAPI()
        nested.add_api_route("/__control/nested", endpoint, methods=["GET"])
        app.router.routes.append(starlette_routing.Mount("/static", app=nested))
        app.router.routes.append(
            starlette_routing.Route("/starlette", endpoint, methods=["GET"])
        )
        app.router.routes.append(
            starlette_routing.WebSocketRoute("/starlette-socket", endpoint)
        )
        app.add_api_websocket_route("/ordinary-socket", endpoint)
        self._install(
            app,
            declaration=_declaration("routing"),
            variables=(RecordingVariable("routing"),),
        )

    def test_current_partial_and_removed_installation_states_are_honest(self) -> None:
        for retained in (4, 3, 2, 1):
            with self.subTest(retained=retained):
                app = self._app()
                self._install(
                    app,
                    declaration=_declaration("routing"),
                    variables=(RecordingVariable("routing"),),
                )
                control = [
                    route
                    for route in app.router.routes
                    if getattr(route, "path", "").startswith("/__control")
                ]
                removed = set(map(id, control[retained:]))
                app.router.routes[:] = [
                    route for route in app.router.routes if id(route) not in removed
                ]
                prior = app.router.routes
                prior_ids = tuple(map(id, prior))
                with self.assertRaisesRegex(
                    ValueError,
                    "FastAPI control routes are already installed",
                ):
                    self._install(
                        app,
                        declaration=_declaration("routing"),
                        variables=(RecordingVariable("routing"),),
                    )
                self.assertIs(app.router.routes, prior)
                self.assertEqual(tuple(map(id, prior)), prior_ids)

        app = self._app()
        self._install(
            app,
            declaration=_declaration("routing"),
            variables=(RecordingVariable("routing"),),
        )
        app.router.routes[:] = [
            route
            for route in app.router.routes
            if not getattr(route, "path", "").startswith("/__control")
        ]
        uninstalled = app.router.routes
        self._install(
            app,
            declaration=_declaration("routing"),
            variables=(RecordingVariable("routing"),),
        )
        self.assertIsNot(app.router.routes, uninstalled)
        self.assertEqual(
            len(
                [
                    route
                    for route in app.router.routes
                    if getattr(route, "path", "").startswith("/__control")
                ]
            ),
            4,
        )

        collided = self._app()
        self._install(
            collided,
            declaration=_declaration("routing"),
            variables=(RecordingVariable("routing"),),
        )
        collided.router.routes[:] = [
            route
            for route in collided.router.routes
            if not getattr(route, "path", "").startswith("/__control")
        ]

        @collided.get("/__control/unmarked")
        async def unmarked_collision() -> dict[str, str]:
            return {"state": "unmarked"}

        prior = collided.router.routes
        prior_ids = tuple(map(id, prior))
        with self.assertRaisesRegex(ValueError, "collides"):
            self._install(
                collided,
                declaration=_declaration("routing"),
                variables=(RecordingVariable("routing"),),
            )
        self.assertIs(collided.router.routes, prior)
        self.assertEqual(tuple(map(id, prior)), prior_ids)

    def test_installer_rejects_after_first_asgi_execution(self) -> None:
        app = self._app()
        cached_schema = app.openapi()
        status, body = asyncio.run(self._asgi_request(app, "GET", "/ordinary"))
        self.assertEqual((status, json.loads(body)), (200, {"message": "ordinary"}))
        self.assertIsNotNone(app.middleware_stack)
        prior = app.router.routes
        prior_ids = tuple(map(id, prior))
        with self.assertRaises(ValueError):
            self._install(
                app,
                declaration=_declaration("routing"),
                variables=(RecordingVariable("routing"),),
            )
        self.assertIs(app.router.routes, prior)
        self.assertEqual(tuple(map(id, prior)), prior_ids)
        self.assertIs(app.openapi(), cached_schema)

    def test_two_apps_have_isolated_registry_target_and_routes(self) -> None:
        first = self._app()
        second = self._app()
        first_variable = RecordingVariable("alpha")
        second_variable = RecordingVariable("beta")
        first_declaration = _declaration("alpha")
        second_declaration = _declaration("beta")
        self._install(first, declaration=first_declaration, variables=(first_variable,))
        self._install(second, declaration=second_declaration, variables=(second_variable,))

        _, first_status, first_body = self._surface_call(
            first,
            first_declaration,
            NodeControlSurfaceReadKind.STATUS,
        )
        _, second_status, second_body = self._surface_call(
            second,
            second_declaration,
            NodeControlSurfaceReadKind.STATUS,
        )
        self.assertEqual((first_status, second_status), (200, 200))
        self.assertEqual(json.loads(first_body)["installed_variable_names"], ["alpha"])
        self.assertEqual(json.loads(second_body)["installed_variable_names"], ["beta"])
        self.assertTrue(
            set(map(id, first.router.routes)).isdisjoint(map(id, second.router.routes))
        )


if __name__ == "__main__":
    unittest.main()
