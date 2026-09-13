from __future__ import annotations

import asyncio
import ast
import base64
from dataclasses import replace
import importlib
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys
from threading import Event, Lock, get_ident
import tomllib
import unittest

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
    DelegationKeyAlgorithm,
    DelegationKeyPurpose,
    DelegationPublicKey,
    MapControlState,
    NodeControlCommandRequest,
    NodeControlEvidence,
    NodeControlEvidenceCode,
    NodeControlFailed,
    NodeControlGraphReference,
    NodeControlGraphReferenceRole,
    NodeControlOperation,
    NodeControlPayload,
    NodeControlReadStateSucceeded,
    NodeControlRejected,
    NodeControlResultCodec,
    NodeControlTarget,
    NodeControlTransitionSucceeded,
    ScalarControlState,
    WorkloadNodeControlSurfaceDeclaration,
    WorkloadNodeControlSurfaceDescriptor,
)
from control_plane_kit_server_sdk import ControlPlaneInvocationContext
from control_plane_kit_server_sdk._replay import _ProcessLocalNodeControlReplay
from control_plane_kit_server_sdk.verification import (
    Ed25519WorkloadNodeControlVerifier,
)
from control_plane_kit_server_sdk.verifier_keys import (
    AtomicWorkloadNodeControlVerifierKeySet,
    WorkloadNodeControlVerifierKeySet,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_NAME = "control_plane_kit_server_sdk._fastapi_variable_routes"
ISSUER = "cpk-server"
AUDIENCE = "workload:router:control"
NOW = 150
MAX_BODY_BYTES = 16_384
MAX_HEADER_BYTES = 32_768
MAX_HEADER_COUNT = 64
MAX_PATH_BYTES = 1_024
MAX_QUERY_BYTES = 1_024

ERRORS = {
    400: {"code": "node-control.request-invalid"},
    401: {"code": "node-control.credential-rejected"},
    403: {"code": "node-control.target-rejected"},
    404: {"code": "node-control.variable-not-found"},
    409: {"code": "node-control.replay-conflict"},
    413: {"code": "node-control.request-too-large"},
    500: {"code": "node-control.internal-failure"},
    503: {"code": "node-control.replay-capacity"},
}


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


def _descriptor(name: str = "routing") -> ControlPlaneVariableDescriptor:
    return ControlPlaneVariableDescriptor(
        variable_name=_reference(NodeControlGraphReferenceRole.VARIABLE, name),
        kind=ControlPlaneVariableKind.SCALAR,
        state_codec=ControlPlaneStateCodec.SCALAR_V1,
        operation_contracts=(
            ControlPlaneVariableOperationContract(
                NodeControlOperation.READ_STATE,
                None,
                ControlPlaneResultCodec.STATE_V1,
            ),
            ControlPlaneVariableOperationContract(
                NodeControlOperation.APPLY_COMMAND,
                ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
                ControlPlaneResultCodec.TRANSITION_V1,
            ),
        ),
    )


def _declaration(*names: str) -> WorkloadNodeControlSurfaceDeclaration:
    return WorkloadNodeControlSurfaceDeclaration(
        WorkloadNodeControlSurfaceDescriptor(
            provider_socket_name=_reference(
                NodeControlGraphReferenceRole.PROVIDER_SOCKET,
                "control",
            ),
            variables=tuple(_descriptor(name) for name in names),
        )
    )


def _request(
    operation: NodeControlOperation,
    *,
    target: NodeControlTarget | None = None,
    variable: str = "routing",
    request_id: str = "request-1",
    key: str = "routing-change-1",
    value: str = "green",
) -> NodeControlCommandRequest:
    values: dict[str, object] = {
        "target": _target() if target is None else target,
        "variable_name": _reference(
            NodeControlGraphReferenceRole.VARIABLE,
            variable,
        ),
        "operation": operation,
        "request_id": request_id,
        "idempotency_key": key,
    }
    if operation is NodeControlOperation.APPLY_COMMAND:
        values.update(
            command_codec=ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
            precondition=ControlPlaneTransitionPrecondition(4),
            payload=NodeControlPayload(
                ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
                ScalarControlState(value),
            ),
        )
    return NodeControlCommandRequest(**values)


def _grant(
    request: NodeControlCommandRequest,
    *,
    key_id: str = "workload-key-a",
) -> DelegatedWorkloadNodeControlGrant:
    return DelegatedWorkloadNodeControlGrant(
        issuer=ISSUER,
        key_id=key_id,
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
        jti="grant-1",
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


def _token(
    private_key: ed25519.Ed25519PrivateKey,
    request: NodeControlCommandRequest,
) -> bytes:
    grant = _grant(request)
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


def _candidate(request: NodeControlCommandRequest) -> bytes:
    return _json_bytes(request.descriptor())


class RecordingVariable:
    def __init__(
        self,
        descriptor: ControlPlaneVariableDescriptor,
        *,
        read_result: object | None = None,
        apply_result: object | None = None,
        apply_gate: tuple[Event, Event] | None = None,
    ) -> None:
        self._descriptor = descriptor
        self.read_result = read_result
        self.apply_result = apply_result
        self.apply_gate = apply_gate
        self.descriptor_calls = 0
        self.read_calls = 0
        self.apply_calls = 0
        self.thread_ids: list[int] = []
        self._lock = Lock()

    def descriptor(self) -> ControlPlaneVariableDescriptor:
        self.descriptor_calls += 1
        return self._descriptor

    def read(self, context: ControlPlaneInvocationContext) -> object:
        with self._lock:
            self.read_calls += 1
            self.thread_ids.append(get_ident())
        if isinstance(self.read_result, BaseException):
            raise self.read_result
        if self.read_result is not None:
            return self.read_result
        return NodeControlReadStateSucceeded(
            context.request.request_id,
            ControlPlaneStateCodec.SCALAR_V1,
            4,
            ScalarControlState("blue"),
        )

    def apply(
        self,
        command: NodeControlCommandRequest,
        context: ControlPlaneInvocationContext,
    ) -> object:
        self.assert_identity = command is context.request
        with self._lock:
            self.apply_calls += 1
            self.thread_ids.append(get_ident())
        if self.apply_gate is not None:
            entered, release = self.apply_gate
            entered.set()
            release.wait(3)
        if isinstance(self.apply_result, BaseException):
            raise self.apply_result
        if self.apply_result is not None:
            return self.apply_result
        return NodeControlTransitionSucceeded(
            command.request_id,
            5,
            NodeControlEvidence(NodeControlEvidenceCode.APPLIED),
        )


class MutableDescriptorVariable(RecordingVariable):
    def replace_descriptor(self, descriptor: ControlPlaneVariableDescriptor) -> None:
        self._descriptor = descriptor


class ThreadRecordingClock:
    def __init__(self, now: int = NOW) -> None:
        self.now = now
        self.thread_ids: list[int] = []
        self.second_call = Event()
        self._lock = Lock()

    def __call__(self) -> int:
        with self._lock:
            self.thread_ids.append(get_ident())
            if len(self.thread_ids) >= 2:
                self.second_call.set()
        return self.now


class FastApiVariableRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.private_key = ed25519.Ed25519PrivateKey.generate()
        public_pem = cls.private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        public_key = DelegationPublicKey(
            "workload-key-a",
            DelegationKeyAlgorithm.ED25519,
            public_pem,
        )
        snapshot = WorkloadNodeControlVerifierKeySet(
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
            (public_key,),
        )
        cls.holder = AtomicWorkloadNodeControlVerifierKeySet(snapshot)
        cls.verifier = Ed25519WorkloadNodeControlVerifier(
            cls.holder,
            expected_issuer=ISSUER,
            expected_audience=AUDIENCE,
            clock=lambda: NOW,
        )

    def _verifier(self, clock) -> Ed25519WorkloadNodeControlVerifier:
        return Ed25519WorkloadNodeControlVerifier(
            self.holder,
            expected_issuer=ISSUER,
            expected_audience=AUDIENCE,
            clock=clock,
        )

    def _module(self):
        specification = importlib.util.find_spec(MODULE_NAME)
        self.assertIsNotNone(
            specification,
            "missing private FastAPI variable-route interpreter",
        )
        return importlib.import_module(MODULE_NAME)

    def _routes(
        self,
        variables: tuple[object, ...],
        *,
        target: NodeControlTarget | None = None,
        declaration: WorkloadNodeControlSurfaceDeclaration | None = None,
        verifier: object | None = None,
        replay: object | None = None,
    ):
        return self._module()._build_variable_routes(
            target=_target() if target is None else target,
            declaration=(
                _declaration("routing")
                if declaration is None
                else declaration
            ),
            variables=variables,
            verifier=self.verifier if verifier is None else verifier,
            replay=(
                _ProcessLocalNodeControlReplay()
                if replay is None
                else replay
            ),
        )

    def _app(self, variable: object, **changes: object):
        fastapi = importlib.import_module("fastapi")
        app = fastapi.FastAPI()

        @app.get("/ordinary")
        async def ordinary() -> dict[str, str]:
            return {"message": "ordinary"}

        app.router.routes.extend(self._routes((variable,), **changes))
        return app

    def _authorization(
        self,
        request: NodeControlCommandRequest,
    ) -> tuple[bytes, bytes]:
        return b"authorization", b"Bearer " + _token(self.private_key, request)

    async def _asgi_request(
        self,
        app,
        method: str,
        path: str,
        *,
        headers: list[tuple[bytes, bytes]] | None = None,
        chunks: tuple[bytes, ...] = (b"",),
        query_string: object = b"",
    ) -> tuple[int, dict[str, object] | None, bytes]:
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
            "client": ("127.0.0.1", 1),
            "server": ("test", 80),
            "root_path": "",
            "state": {},
        }
        await app(scope, receive, send)
        start = next(message for message in sent if message["type"] == "http.response.start")
        body = b"".join(
            message.get("body", b"")
            for message in sent
            if message["type"] == "http.response.body"
        )
        content = json.loads(body) if body else None
        return int(start["status"]), content, body

    def _call(self, *args: object, **kwargs: object):
        return asyncio.run(self._asgi_request(*args, **kwargs))

    def _read(
        self,
        app,
        request: NodeControlCommandRequest | None = None,
        *,
        headers: list[tuple[bytes, bytes]] | None = None,
        chunks: tuple[bytes, ...] = (b"",),
        variable: str = "routing",
    ):
        selected = _request(NodeControlOperation.READ_STATE) if request is None else request
        return self._call(
            app,
            "GET",
            f"/__control/variables/{variable}",
            headers=[self._authorization(selected)] if headers is None else headers,
            chunks=chunks,
        )

    def _apply(
        self,
        app,
        request: NodeControlCommandRequest | None = None,
        *,
        headers: list[tuple[bytes, bytes]] | None = None,
        chunks: tuple[bytes, ...] | None = None,
        variable: str = "routing",
    ):
        selected = _request(NodeControlOperation.APPLY_COMMAND) if request is None else request
        return self._call(
            app,
            "POST",
            f"/__control/variables/{variable}/commands",
            headers=[self._authorization(selected)] if headers is None else headers,
            chunks=(_candidate(selected),) if chunks is None else chunks,
        )

    def assert_error(self, response, status: int) -> None:
        actual_status, content, body = response
        self.assertEqual(actual_status, status)
        self.assertEqual(content, ERRORS[status])
        self.assertLessEqual(len(body), 128)

    def test_optional_dependency_is_exact_and_root_stays_lazy(self) -> None:
        metadata = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text())
        optional_dependencies = metadata["project"]["optional-dependencies"]
        self.assertIn("fastapi", optional_dependencies)
        self.assertEqual(
            optional_dependencies.get("fastapi"),
            [
                "PyJWT==2.13.0",
                "cryptography==50.0.0",
                "fastapi==0.141.1",
                "starlette==1.6.0",
            ],
        )
        root = importlib.import_module("control_plane_kit_server_sdk")
        self.assertNotIn("install_cpk_control_routes", root.__all__)
        self.assertFalse(hasattr(root, "install_cpk_control_routes"))

        script = """
import sys
import control_plane_kit_server_sdk

for name in ("fastapi", "starlette", "anyio", "jwt", "cryptography"):
    assert name not in sys.modules, name
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_builder_returns_only_exact_command_routes(self) -> None:
        variable = RecordingVariable(_descriptor())
        routes = self._routes((variable,))
        observed = {
            (method, route.path)
            for route in routes
            for method in route.methods
        }
        self.assertEqual(
            observed,
            {
                ("GET", "/__control/variables/{variable_name}"),
                ("POST", "/__control/variables/{variable_name}/commands"),
            },
        )
        self.assertEqual(variable.descriptor_calls, 1)

    def test_registry_accepts_empty_or_declared_subset_and_snapshots_once(self) -> None:
        self.assertEqual(
            len(self._routes((), declaration=_declaration("routing"))),
            2,
        )
        alpha = RecordingVariable(_descriptor("alpha"))
        routes = self._routes(
            (alpha,),
            declaration=_declaration("alpha", "beta"),
        )
        self.assertEqual(len(routes), 2)
        self.assertEqual(alpha.descriptor_calls, 1)

        read_route = next(
            route
            for route in routes
            if route.path == "/__control/variables/{variable_name}"
        )
        registry = inspect.getclosurevars(read_route.endpoint).nonlocals["registry"]
        self.assertEqual(len(registry["alpha"]), 3)
        registered_variable, registered_descriptor, registered_codec = registry["alpha"]
        self.assertIs(registered_variable, alpha)
        self.assertEqual(registered_descriptor, _descriptor("alpha"))
        self.assertIsInstance(registered_codec, NodeControlResultCodec)

        alpha._descriptor = _descriptor("beta")
        fastapi = importlib.import_module("fastapi")
        app = fastapi.FastAPI()
        app.router.routes.extend(routes)
        request = _request(NodeControlOperation.READ_STATE, variable="alpha")
        status, content, _ = self._read(app, request, variable="alpha")
        self.assertEqual(status, 200)
        self.assertEqual(content["request_id"], request.request_id)
        self.assertEqual(alpha.descriptor_calls, 1)

    def test_registry_rejects_bad_shape_before_route_construction(self) -> None:
        cases = (
            ((RecordingVariable(_descriptor("extra")),), _declaration("routing")),
            (
                (
                    RecordingVariable(_descriptor("routing")),
                    RecordingVariable(_descriptor("routing")),
                ),
                _declaration("routing"),
            ),
            ((object(),), _declaration("routing")),
            ([RecordingVariable(_descriptor())], _declaration("routing")),
        )
        for variables, declaration in cases:
            with self.subTest(variables=variables):
                with self.assertRaises(ValueError):
                    self._routes(variables, declaration=declaration)

        wrong_socket = replace(
            _target(),
            provider_socket_name=_reference(
                NodeControlGraphReferenceRole.PROVIDER_SOCKET,
                "other-control",
            ),
        )
        with self.assertRaises(ValueError):
            self._routes(
                (RecordingVariable(_descriptor()),),
                target=wrong_socket,
            )

    def test_read_and_apply_publish_exact_closed_results(self) -> None:
        variable = RecordingVariable(_descriptor())
        app = self._app(variable)
        read = _request(NodeControlOperation.READ_STATE)
        status, content, body = self._read(app, read)
        self.assertEqual(status, 200)
        self.assertEqual(
            content,
            NodeControlReadStateSucceeded(
                read.request_id,
                ControlPlaneStateCodec.SCALAR_V1,
                4,
                ScalarControlState("blue"),
            ).descriptor(),
        )
        self.assertEqual(body, _json_bytes(content))
        self.assertLessEqual(len(body), MAX_BODY_BYTES)

        apply = _request(NodeControlOperation.APPLY_COMMAND)
        status, content, body = self._apply(app, apply)
        self.assertEqual(status, 200)
        self.assertEqual(
            content,
            NodeControlTransitionSucceeded(
                apply.request_id,
                5,
                NodeControlEvidence(NodeControlEvidenceCode.APPLIED),
            ).descriptor(),
        )
        self.assertEqual(body, _json_bytes(content))
        self.assertLessEqual(len(body), MAX_BODY_BYTES)
        self.assertTrue(variable.assert_identity)

    def test_rejected_and_failed_core_results_remain_nominal_http_results(self) -> None:
        cases = (
            (
                NodeControlOperation.READ_STATE,
                NodeControlRejected,
                NodeControlEvidenceCode.NOT_AUTHORIZED,
            ),
            (NodeControlOperation.READ_STATE, NodeControlFailed, None),
            (
                NodeControlOperation.APPLY_COMMAND,
                NodeControlRejected,
                NodeControlEvidenceCode.PRECONDITION_FAILED,
            ),
            (NodeControlOperation.APPLY_COMMAND, NodeControlFailed, None),
        )
        for operation, result_type, evidence_code in cases:
            with self.subTest(operation=operation, result_type=result_type):
                request = _request(operation)
                if result_type is NodeControlRejected:
                    result = result_type(
                        request.request_id,
                        operation,
                        NodeControlEvidence(evidence_code),
                    )
                else:
                    result = result_type(request.request_id, operation)
                variable = RecordingVariable(
                    _descriptor(),
                    read_result=result,
                    apply_result=result,
                )
                response = (
                    self._read(self._app(variable), request)
                    if operation is NodeControlOperation.READ_STATE
                    else self._apply(self._app(variable), request)
                )
                status, content, body = response
                self.assertEqual(status, 200)
                self.assertEqual(content, result.descriptor())
                self.assertEqual(body, _json_bytes(result.descriptor()))

    def test_invalid_result_and_variable_exception_are_closed(self) -> None:
        read = _request(NodeControlOperation.READ_STATE)
        cases = (
            object(),
            NodeControlFailed("wrong-request", NodeControlOperation.READ_STATE),
            NodeControlFailed(read.request_id, NodeControlOperation.APPLY_COMMAND),
            RuntimeError("authorization: Bearer provider-secret"),
        )
        for result in cases:
            with self.subTest(result=type(result).__name__):
                variable = RecordingVariable(_descriptor(), read_result=result)
                self.assert_error(self._read(self._app(variable), read), 500)
                self.assertEqual(variable.read_calls, 1)

        wrong_state = NodeControlReadStateSucceeded(
            read.request_id,
            ControlPlaneStateCodec.MAP_V1,
            4,
            MapControlState((("route", "blue"),)),
        )
        self.assert_error(
            self._read(
                self._app(
                    RecordingVariable(_descriptor(), read_result=wrong_state)
                ),
                read,
            ),
            500,
        )

        apply = _request(NodeControlOperation.APPLY_COMMAND)
        for result in (
            NodeControlFailed("wrong-request", NodeControlOperation.APPLY_COMMAND),
            NodeControlFailed(apply.request_id, NodeControlOperation.READ_STATE),
        ):
            with self.subTest(apply_result=result):
                status, content, body = self._apply(
                    self._app(
                        RecordingVariable(_descriptor(), apply_result=result)
                    ),
                    apply,
                )
                expected = NodeControlFailed(
                    apply.request_id,
                    NodeControlOperation.APPLY_COMMAND,
                ).descriptor()
                self.assertEqual(status, 200)
                self.assertEqual(content, expected)
                self.assertEqual(body, _json_bytes(expected))

        class OversizedReadResult(NodeControlReadStateSucceeded):
            emit_oversized = False

            def descriptor(self) -> dict[str, object]:
                descriptor = super().descriptor()
                if self.emit_oversized:
                    descriptor["padding"] = "x" * (MAX_BODY_BYTES + 1)
                return descriptor

        oversized = OversizedReadResult(
            read.request_id,
            ControlPlaneStateCodec.SCALAR_V1,
            4,
            ScalarControlState("blue"),
        )
        OversizedReadResult.emit_oversized = True
        self.assert_error(
            self._read(
                self._app(
                    RecordingVariable(_descriptor(), read_result=oversized)
                ),
                read,
            ),
            500,
        )

    def test_missing_malformed_duplicate_and_alternate_credentials_reject(self) -> None:
        variable = RecordingVariable(_descriptor())
        app = self._app(variable)
        request = _request(NodeControlOperation.READ_STATE)
        valid = self._authorization(request)
        cases = (
            [],
            [(b"authorization", b"Basic value")],
            [(b"authorization", b"Bearer")],
            [valid, valid],
            [(b"x-control-plane-token", b"static-token")],
        )
        for headers in cases:
            with self.subTest(headers=len(headers)):
                self.assert_error(self._read(app, request, headers=headers), 401)
        self.assertEqual(variable.read_calls, 0)

    def test_transport_bounds_and_bodyless_read_precede_application(self) -> None:
        variable = RecordingVariable(_descriptor())
        app = self._app(variable)
        read = _request(NodeControlOperation.READ_STATE)
        self.assert_error(self._read(app, read, chunks=(b"x",)), 400)
        self.assert_error(self._read(app, read, chunks=(b"", b"hidden")), 400)

        accepted_headers = [self._authorization(read)] + [
            (f"x-{index}".encode("ascii"), b"x")
            for index in range(MAX_HEADER_COUNT - 1)
        ]
        accepted_variable = RecordingVariable(_descriptor())
        self.assertEqual(
            self._read(
                self._app(accepted_variable),
                read,
                headers=accepted_headers,
            )[0],
            200,
        )
        self.assertEqual(accepted_variable.read_calls, 1)

        huge_headers = [
            self._authorization(read),
            (b"x-padding", b"x" * MAX_HEADER_BYTES),
        ]
        self.assert_error(self._read(app, read, headers=huge_headers), 413)
        authorization = self._authorization(read)
        exact_header_value_size = MAX_HEADER_BYTES - sum(
            len(name) + len(value) for name, value in (authorization,)
        ) - len(b"x-padding")
        exact_header_variable = RecordingVariable(_descriptor())
        self.assertEqual(
            self._read(
                self._app(exact_header_variable),
                read,
                headers=[
                    authorization,
                    (b"x-padding", b"x" * exact_header_value_size),
                ],
            )[0],
            200,
        )
        self.assertEqual(exact_header_variable.read_calls, 1)
        too_many_headers = [self._authorization(read)] + [
            (f"x-{index}".encode("ascii"), b"x")
            for index in range(MAX_HEADER_COUNT)
        ]
        self.assert_error(self._read(app, read, headers=too_many_headers), 413)

        apply = _request(NodeControlOperation.APPLY_COMMAND)
        self.assert_error(
            self._apply(app, apply, chunks=(b"x" * (MAX_BODY_BYTES + 1),)),
            413,
        )
        self.assert_error(
            self._apply(
                app,
                apply,
                chunks=(b"x" * 4_096,) * 4 + (b"x",),
            ),
            413,
        )
        self.assert_error(
            self._apply(app, apply, chunks=(b"x" * MAX_BODY_BYTES,)),
            401,
        )

        prefix = "/__control/variables/"
        exact_path = prefix + "x" * (MAX_PATH_BYTES - len(prefix))
        over_path = prefix + "x" * (MAX_PATH_BYTES - len(prefix) + 1)
        exact_response = self._call(
            app,
            "GET",
            exact_path,
            headers=[self._authorization(read)],
        )
        self.assertEqual(len(exact_path.encode("ascii")), MAX_PATH_BYTES)
        self.assert_error(exact_response, 400)
        self.assertEqual(len(over_path.encode("ascii")), MAX_PATH_BYTES + 1)
        self.assert_error(
            self._call(
                app,
                "GET",
                over_path,
                headers=[self._authorization(read)],
            ),
            413,
        )
        self.assertEqual(variable.read_calls, 0)
        self.assertEqual(variable.apply_calls, 0)

    def test_query_input_rejects_before_admission_registry_replay_or_variable(self) -> None:
        for operation in NodeControlOperation:
            for identity, query_string, expected_status in (
                ("nonempty", b"ignored=true", 400),
                ("oversized", b"x" * (MAX_QUERY_BYTES + 1), 413),
            ):
                with self.subTest(operation=operation, identity=identity):
                    clock = ThreadRecordingClock()
                    replay = _ProcessLocalNodeControlReplay()
                    variable = RecordingVariable(_descriptor())
                    app = self._app(
                        variable,
                        verifier=self._verifier(clock),
                        replay=replay,
                    )
                    request = _request(
                        operation,
                        request_id=f"query-{operation.value}-{identity}",
                        key=f"query-{operation.value}-{identity}",
                    )
                    path = "/__control/variables/routing"
                    chunks = (b"",)
                    if operation is NodeControlOperation.APPLY_COMMAND:
                        path += "/commands"
                        chunks = (_candidate(request),)
                    response = self._call(
                        app,
                        "GET" if operation is NodeControlOperation.READ_STATE else "POST",
                        path,
                        headers=[self._authorization(request)],
                        chunks=chunks,
                        query_string=query_string,
                    )

                    self.assert_error(response, expected_status)
                    self.assertEqual(clock.thread_ids, [])
                    self.assertEqual(variable.read_calls, 0)
                    self.assertEqual(variable.apply_calls, 0)
                    self.assertEqual(replay._entries, {})

        module = self._module()
        self.assertTrue(
            hasattr(module, "_query_status"),
            "missing private raw query classifier",
        )
        self.assertEqual(module._query_status(object()), 400)

    def test_fragmented_apply_reconstructs_the_exact_candidate(self) -> None:
        variable = RecordingVariable(_descriptor())
        app = self._app(variable)
        request = _request(NodeControlOperation.APPLY_COMMAND)
        candidate = _candidate(request)
        cut_one = len(candidate) // 3
        cut_two = 2 * len(candidate) // 3

        response = self._apply(
            app,
            request,
            chunks=(candidate[:cut_one], candidate[cut_one:cut_two], candidate[cut_two:]),
        )

        self.assertEqual(response[0], 200)
        self.assertEqual(variable.apply_calls, 1)

    def test_invalid_apply_candidate_rejects_before_replay_or_variable(self) -> None:
        variable = RecordingVariable(_descriptor())
        app = self._app(variable)
        request = _request(NodeControlOperation.APPLY_COMMAND)
        self.assert_error(self._apply(app, request, chunks=(b"not-json",)), 401)
        self.assertEqual(self._apply(app, request)[0], 200)
        self.assertEqual(variable.apply_calls, 1)

    def test_same_audience_nonlocal_targets_reject_before_registry(self) -> None:
        substitutions = (
            replace(
                _target(),
                workspace_id=_reference(
                    NodeControlGraphReferenceRole.WORKSPACE,
                    "workspace-2",
                ),
            ),
            replace(
                _target(),
                graph_revision=_reference(
                    NodeControlGraphReferenceRole.GRAPH_REVISION,
                    "revision-8",
                ),
            ),
            replace(
                _target(),
                node_id=_reference(NodeControlGraphReferenceRole.NODE, "other-router"),
            ),
            replace(
                _target(),
                provider_socket_name=_reference(
                    NodeControlGraphReferenceRole.PROVIDER_SOCKET,
                    "other-control",
                ),
            ),
        )
        for operation in NodeControlOperation:
            for index, target in enumerate(substitutions):
                with self.subTest(operation=operation, target=target):
                    variable = RecordingVariable(_descriptor())
                    app = self._app(variable)
                    request = _request(
                        operation,
                        target=target,
                        request_id=f"nonlocal-{operation.value}-{index}",
                        key=f"nonlocal-{operation.value}-{index}",
                    )
                    response = (
                        self._read(app, request)
                        if operation is NodeControlOperation.READ_STATE
                        else self._apply(app, request)
                    )
                    self.assert_error(response, 403)
                    self.assertEqual(variable.read_calls, 0)
                    self.assertEqual(variable.apply_calls, 0)

        variable = RecordingVariable(_descriptor())
        app = self._app(variable)
        wrong_apply = _request(
            NodeControlOperation.APPLY_COMMAND,
            target=substitutions[0],
            key="nonlocal-key",
        )
        self.assert_error(self._apply(app, wrong_apply), 403)
        local_apply = _request(
            NodeControlOperation.APPLY_COMMAND,
            key="nonlocal-key",
        )
        self.assertEqual(self._apply(app, local_apply)[0], 200)
        self.assertEqual(variable.apply_calls, 1)

        for operation in NodeControlOperation:
            with self.subTest(operation=operation, precedence="missing"):
                nonlocal_missing = _request(
                    operation,
                    target=substitutions[0],
                    variable="missing",
                    request_id=f"nonlocal-missing-{operation.value}",
                    key=f"nonlocal-missing-{operation.value}",
                )
                nonlocal_response = (
                    self._read(app, nonlocal_missing, variable="missing")
                    if operation is NodeControlOperation.READ_STATE
                    else self._apply(app, nonlocal_missing, variable="missing")
                )
                self.assert_error(nonlocal_response, 403)

                local_missing = _request(
                    operation,
                    variable="missing",
                    request_id=f"local-missing-{operation.value}",
                    key=f"local-missing-{operation.value}",
                )
                local_response = (
                    self._read(app, local_missing, variable="missing")
                    if operation is NodeControlOperation.READ_STATE
                    else self._apply(app, local_missing, variable="missing")
                )
                self.assert_error(local_response, 404)

    def test_route_operation_and_variable_binding_precede_lookup(self) -> None:
        variable = RecordingVariable(_descriptor())
        app = self._app(variable)
        apply = _request(NodeControlOperation.APPLY_COMMAND)
        self.assert_error(self._read(app, apply), 401)

        other = _request(NodeControlOperation.READ_STATE, variable="other")
        self.assert_error(self._read(app, other, variable="routing"), 401)

        missing = _request(NodeControlOperation.READ_STATE, variable="missing")
        self.assert_error(self._read(app, missing, variable="missing"), 404)
        self.assertEqual(variable.read_calls, 0)

    def test_apply_replay_converges_and_changed_intent_conflicts(self) -> None:
        variable = RecordingVariable(_descriptor())
        app = self._app(variable)
        first = _request(NodeControlOperation.APPLY_COMMAND)
        first_response = self._apply(app, first)
        replay_response = self._apply(app, first)
        self.assertEqual(first_response, replay_response)
        self.assertEqual(variable.apply_calls, 1)

        changed = _request(
            NodeControlOperation.APPLY_COMMAND,
            request_id="request-2",
            value="blue",
        )
        self.assert_error(self._apply(app, changed), 409)
        self.assertEqual(variable.apply_calls, 1)

    def test_every_replay_attempt_authenticates_first(self) -> None:
        variable = RecordingVariable(_descriptor())
        app = self._app(variable)
        request = _request(NodeControlOperation.APPLY_COMMAND)
        self.assertEqual(self._apply(app, request)[0], 200)
        invalid = [(b"authorization", b"Bearer invalid")]
        self.assert_error(self._apply(app, request, headers=invalid), 401)
        self.assertEqual(variable.apply_calls, 1)

    def test_replay_capacity_is_bounded_and_app_local(self) -> None:
        first_variable = RecordingVariable(_descriptor())
        first_app = self._app(
            first_variable,
            replay=_ProcessLocalNodeControlReplay(capacity=1),
        )
        request = _request(NodeControlOperation.APPLY_COMMAND)
        self.assertEqual(self._apply(first_app, request)[0], 200)
        unrelated = _request(
            NodeControlOperation.APPLY_COMMAND,
            request_id="request-2",
            key="routing-change-2",
        )
        self.assert_error(self._apply(first_app, unrelated), 503)

        second_variable = RecordingVariable(_descriptor())
        second_app = self._app(
            second_variable,
            replay=_ProcessLocalNodeControlReplay(capacity=1),
        )
        self.assertEqual(self._apply(second_app, unrelated)[0], 200)
        self.assertEqual(first_variable.apply_calls, 1)
        self.assertEqual(second_variable.apply_calls, 1)

    def test_concurrent_apply_has_one_worker_and_convergent_waiter(self) -> None:
        entered = Event()
        release = Event()
        variable = RecordingVariable(
            _descriptor(),
            apply_gate=(entered, release),
        )
        clock = ThreadRecordingClock()
        replay = _ProcessLocalNodeControlReplay()
        app = self._app(
            variable,
            verifier=self._verifier(clock),
            replay=replay,
        )
        request = _request(NodeControlOperation.APPLY_COMMAND)

        async def scenario():
            first = asyncio.create_task(
                self._asgi_request(
                    app,
                    "POST",
                    "/__control/variables/routing/commands",
                    headers=[self._authorization(request)],
                    chunks=(_candidate(request),),
                )
            )
            await asyncio.to_thread(entered.wait, 3)
            second = asyncio.create_task(
                self._asgi_request(
                    app,
                    "POST",
                    "/__control/variables/routing/commands",
                    headers=[self._authorization(request)],
                    chunks=(_candidate(request),),
                )
            )
            self.assertTrue(await asyncio.to_thread(clock.second_call.wait, 3))

            deadline = asyncio.get_running_loop().time() + 3
            while True:
                with replay._condition:
                    waiter_count = len(replay._condition._waiters)
                if waiter_count == 1:
                    break
                self.assertLess(asyncio.get_running_loop().time(), deadline)
                await asyncio.sleep(0)

            loop_progressed = False

            async def mark_loop_progress() -> None:
                nonlocal loop_progressed
                await asyncio.sleep(0)
                loop_progressed = True

            await mark_loop_progress()
            self.assertTrue(loop_progressed)
            self.assertFalse(first.done())
            release.set()
            return await asyncio.gather(first, second)

        responses = asyncio.run(scenario())
        self.assertEqual(responses[0], responses[1])
        self.assertEqual(variable.apply_calls, 1)

    def test_source_has_one_explicit_threadpool_handoff(self) -> None:
        module = self._module()
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=module.__file__)
        imported = [
            alias.asname or alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "fastapi.concurrency"
            for alias in node.names
            if alias.name == "run_in_threadpool"
        ]
        awaited_calls = [
            node.value.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Await)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
        ]
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        called_attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }

        self.assertEqual(imported, ["run_in_threadpool"])
        self.assertEqual(awaited_calls.count("run_in_threadpool"), 1)
        self.assertTrue(
            {"to_thread", "run_in_executor", "run_sync", "iterate_in_threadpool"}
            .isdisjoint(called_names | called_attributes)
        )

    def test_source_constructs_result_codec_only_during_registry_snapshot(self) -> None:
        module = importlib.import_module("control_plane_kit_server_sdk._control_dispatch")
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=module.__file__)
        codec_calls: list[tuple[str, int]] = []
        for function in (
            node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ):
            for node in ast.walk(function):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "NodeControlResultCodec"
                ):
                    codec_calls.append((function.name, node.lineno))

        self.assertEqual(
            [name for name, _line in codec_calls],
            ["_build_variable_registry"],
        )

    def test_verifier_through_variable_execution_runs_off_event_loop(self) -> None:
        clock = ThreadRecordingClock()
        variable = RecordingVariable(_descriptor())
        app = self._app(variable, verifier=self._verifier(clock))

        async def scenario():
            event_loop_thread = get_ident()
            response = await self._asgi_request(
                app,
                "GET",
                "/__control/variables/routing",
                headers=[self._authorization(_request(NodeControlOperation.READ_STATE))],
            )
            return event_loop_thread, response

        event_loop_thread, response = asyncio.run(scenario())
        self.assertEqual(response[0], 200)
        self.assertEqual(len(variable.thread_ids), 1)
        self.assertEqual(len(clock.thread_ids), 1)
        self.assertNotEqual(variable.thread_ids[0], event_loop_thread)
        self.assertEqual(clock.thread_ids[0], variable.thread_ids[0])

    def test_ordinary_application_route_is_unchanged(self) -> None:
        variable = RecordingVariable(_descriptor())
        app = self._app(variable)
        status, content, _ = self._call(app, "GET", "/ordinary")
        self.assertEqual(status, 200)
        self.assertEqual(content, {"message": "ordinary"})
        self.assertEqual(variable.read_calls, 0)
        self.assertEqual(variable.apply_calls, 0)

    def test_errors_and_private_objects_are_bounded_and_redacted(self) -> None:
        variable = RecordingVariable(
            _descriptor(),
            read_result=RuntimeError("authorization: Bearer secret-value"),
        )
        app = self._app(variable)
        responses = (
            self._read(app, headers=[(b"authorization", b"Bearer secret-token")]),
            self._read(
                app,
                _request(
                    NodeControlOperation.READ_STATE,
                    target=replace(
                        _target(),
                        node_id=_reference(
                            NodeControlGraphReferenceRole.NODE,
                            "private-node",
                        ),
                    ),
                ),
            ),
            self._read(app, _request(NodeControlOperation.READ_STATE)),
        )
        forbidden = (
            "secret",
            "private-node",
            "workspace-1",
            "revision-7",
            "routing",
            "provider",
            "Bearer",
        )
        for response in responses:
            rendered = repr(response)
            self.assertFalse(any(value in rendered for value in forbidden))
            self.assertIn(response[0], ERRORS)


if __name__ == "__main__":
    unittest.main()
