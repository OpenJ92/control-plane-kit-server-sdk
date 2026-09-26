"""Configuration-driven real hosts, default lifecycle and signed denial laws."""
import asyncio
from contextlib import asynccontextmanager, contextmanager
from dataclasses import replace
import importlib
import importlib.util
import json
import os
from pathlib import Path
from http.server import HTTPServer
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time
import unittest
from unittest.mock import patch

import control_plane_kit_core as core
from control_plane_kit_core.wrapper_configuration import (
    NodeControlVerificationConfiguration, WorkloadNodeControlConfiguration,
    WorkloadNodeControlConfigurationCodec, WORKLOAD_NODE_CONTROL_CONFIGURATION_ENVIRONMENT,
)
from control_plane_kit_server_sdk import fastapi as fastapi_sdk, stdlib as stdlib_sdk
from tests import test_fastapi_control_routes as legacy
from tests import test_fastapi_health_routes as asgi_fixtures
from tests import test_health_verification as credentials
from tests import test_stdlib_control as http_fixtures

MODULE = "control_plane_kit_server_sdk.wrapper"


class WrapperSetupTests(unittest.TestCase):
    def setUp(self):
        self.fixture = credentials.SignedHealthReadVerificationTests()
        self.fixture.setUp()
        self.legacy = legacy.FastApiControlRouteTests()
        self.legacy.setUpClass()
        self.config = WorkloadNodeControlConfiguration(
            self.fixture.target, self.fixture.runtime, self.fixture.declaration,
            (NodeControlVerificationConfiguration(core.DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
                legacy.ISSUER, (core.DelegationPublicKey("surface-key-a", core.DelegationKeyAlgorithm.ED25519,
                    legacy._public_pem(self.legacy.surface_private)),)),
             NodeControlVerificationConfiguration(core.DelegationKeyPurpose.WORKLOAD_NODE_HEALTH_READ,
                self.fixture.grant().issuer, (self.fixture.key,))))
        # Accepted merged Core and genuine signed fixtures must work before target red.
        self.encoded = WorkloadNodeControlConfigurationCodec().encode_bytes(self.config)
        self.assertEqual(WorkloadNodeControlConfigurationCodec().decode_bytes(self.encoded), self.config)
        self.assertIsNotNone(importlib.util.find_spec(MODULE), "automatic wrapper setup is not implemented")
        self.api = importlib.import_module(MODULE)

    @contextmanager
    def delivered(self, encoded=None):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "arbitrary-product-config.json"
            path.write_bytes(self.encoded if encoded is None else encoded)
            path.chmod(0o444)
            with patch.dict(os.environ, {WORKLOAD_NODE_CONTROL_CONFIGURATION_ENVIRONMENT: str(path)}):
                yield path

    def refusal(self, action):
        with self.assertRaises(self.api.WrapperSetupError) as caught:
            action()
        self.assertEqual(str(caught.exception), "wrapper setup is invalid")
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)

    def install(self, app, **changes):
        install = getattr(fastapi_sdk, "install_cpk_wrapper", None)
        self.assertIsNotNone(install, "automatic FastAPI wrapper is missing")
        install(app, clock=lambda: 150, **changes)

    async def asgi(self, app, *, kind=core.NodeHealthReadKind.READINESS, token=None, target=None):
        request = replace(self.fixture.request, kind=kind, target=self.fixture.target if target is None else target)
        signed = self.fixture.token(self.fixture.grant(request,
            audience=core.workload_node_control_audience(request.target))) if token is None else token
        helper = asgi_fixtures.FastApiHealthRouteTests()
        helper.fixture = self.fixture
        status, _, body = await helper.asgi(app, path="/__control/health/" + kind.value, token=signed)
        if status == 200:
            return status, core.NodeHealthReadResultCodec(request, self.fixture.declaration).decode(json.loads(body)).outcome
        return status, body

    def test_opened_file_loader_is_bounded_readonly_and_does_not_expose_inputs(self):
        with self.delivered() as path:
            self.assertEqual(self.api.load_wrapper_configuration(), self.config)
            path.chmod(0o644)
            self.refusal(self.api.load_wrapper_configuration)
            path.chmod(0o444)
            linked = path.with_name("link.json")
            linked.symlink_to(path)
            with patch.dict(os.environ, {WORKLOAD_NODE_CONTROL_CONFIGURATION_ENVIRONMENT: str(linked)}):
                self.refusal(self.api.load_wrapper_configuration)
            with patch.dict(os.environ, {WORKLOAD_NODE_CONTROL_CONFIGURATION_ENVIRONMENT: str(path.parent)}):
                self.refusal(self.api.load_wrapper_configuration)
        with patch.dict(os.environ, {}, clear=True):
            self.refusal(self.api.load_wrapper_configuration)
        for value in (b"private-canary", b"x" * 65537,
                      self.encoded.replace(b"workload-node-control-configuration.v1", b"workload-node-control-configuration.v9")):
            with self.delivered(value):
                self.refusal(self.api.load_wrapper_configuration)

    def test_fastapi_defaults_preserve_lifespan_and_report_only_observed_lifecycle(self):
        async def exercise():
            events = []
            state = {"business_state": "retained"}
            @asynccontextmanager
            async def lifespan(app):
                events.append("startup")
                try:
                    yield state
                finally:
                    self.assertEqual((await self.asgi(app))[1], core.NodeHealthReadOutcome.UNHEALTHY)
                    events.append("shutdown")
            app = self.legacy._app()
            app.router.lifespan_context = lifespan
            with self.delivered() as path:
                self.install(app)
                # Snapshot the delivered config once; later file changes are not authority reload.
                path.chmod(0o644)
                path.write_bytes(b"later-invalid")
                path.chmod(0o444)
                self.assertEqual((await self.asgi(app))[1], core.NodeHealthReadOutcome.UNHEALTHY)
                self.assertEqual((await self.asgi(app, kind=core.NodeHealthReadKind.LIVENESS))[1], core.NodeHealthReadOutcome.HEALTHY)
                async with app.router.lifespan_context(app) as actual:
                    self.assertIs(actual, state)
                    self.assertEqual((await self.asgi(app))[1], core.NodeHealthReadOutcome.HEALTHY)
                    self.assertEqual((await self.asgi(app, token=b"invalid"))[0], 401)
                    helper = asgi_fixtures.FastApiHealthRouteTests()
                    helper.fixture = self.fixture
                    static_request = legacy._surface_request(self.fixture.declaration,
                        core.NodeControlSurfaceReadKind.STATUS, target=self.fixture.target)
                    code, _, _ = await helper.asgi(app, path="/__control/status",
                        token=legacy._surface_token(self.legacy.surface_private, static_request))
                    self.assertEqual(code, 200)
                    code, _, body = await helper.asgi(app, path="/ordinary", headers=[])
                    self.assertEqual((code, json.loads(body)), (200, {"message": "ordinary"}))
                self.assertEqual((await self.asgi(app))[1], core.NodeHealthReadOutcome.UNHEALTHY)
            self.assertEqual(events, ["startup", "shutdown"])
        asyncio.run(exercise())

    def test_two_instances_keep_configured_identity_and_lifecycle_separate(self):
        async def exercise():
            other_target = replace(self.fixture.target, node_id=replace(self.fixture.target.node_id, value="other"))
            other_config = replace(self.config, target=other_target)
            first, second = self.legacy._app(), self.legacy._app()
            with self.delivered():
                self.install(first)
            with self.delivered(WorkloadNodeControlConfigurationCodec().encode_bytes(other_config)):
                self.install(second)
            async with first.router.lifespan_context(first):
                self.assertEqual((await self.asgi(first))[1], core.NodeHealthReadOutcome.HEALTHY)
                self.assertEqual((await self.asgi(second))[0], 401)
                self.assertEqual((await self.asgi(second, target=other_target))[1], core.NodeHealthReadOutcome.UNHEALTHY)
                async with second.router.lifespan_context(second):
                    self.assertEqual((await self.asgi(second, target=other_target))[1], core.NodeHealthReadOutcome.HEALTHY)
                self.assertEqual((await self.asgi(first))[1], core.NodeHealthReadOutcome.HEALTHY)
        asyncio.run(exercise())

    def test_mixed_configuration_builds_real_command_authority_without_parallel_dispatch(self):
        declaration = replace(self.fixture.declaration, surface=replace(self.fixture.declaration.surface,
            variables=(legacy._descriptor("routing"),)))
        command = NodeControlVerificationConfiguration(core.DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
            legacy.ISSUER, (core.DelegationPublicKey("workload-key-a", core.DelegationKeyAlgorithm.ED25519,
                legacy._public_pem(self.legacy.command_private)),))
        config = replace(self.config, declaration=declaration, verifiers=(*self.config.verifiers, command))
        variable = legacy.RecordingVariable("routing")
        app = self.legacy._app()
        with self.delivered(WorkloadNodeControlConfigurationCodec().encode_bytes(config)):
            self.install(app, variables=(variable,))
        request = legacy._command_request(core.NodeControlOperation.APPLY_COMMAND, target=self.fixture.target)
        for _ in range(2):
            self.assertEqual(asyncio.run(self.legacy._command_call(app, request))[0], 200)
        self.assertEqual(variable.apply_calls, 1)

    def test_fastapi_startup_failure_and_collision_do_not_claim_ready_or_publish_partial_setup(self):
        async def exercise():
            marker = RuntimeError("application startup failed")
            @asynccontextmanager
            async def failed(app):
                raise marker
                yield
            app = self.legacy._app()
            app.router.lifespan_context = failed
            with self.delivered():
                self.install(app)
                with self.assertRaises(RuntimeError) as caught:
                    async with app.router.lifespan_context(app):
                        self.fail("startup unexpectedly completed")
                self.assertIs(caught.exception, marker)
                self.assertEqual((await self.asgi(app))[1], core.NodeHealthReadOutcome.UNHEALTHY)
                other = self.legacy._app()
                other.add_api_route("/__control/occupied", lambda: {})
                prior_routes, prior_lifespan = other.router.routes, other.router.lifespan_context
                with self.assertRaises(ValueError):
                    self.install(other)
                self.assertIs(other.router.routes, prior_routes)
                self.assertIs(other.router.lifespan_context, prior_lifespan)
        asyncio.run(exercise())

    def test_optional_checks_are_authenticated_and_cannot_override_stopped_lifecycle(self):
        async def exercise():
            calls = []
            def check():
                calls.append(1)
                return core.NodeHealthReadOutcome.HEALTHY
            app = self.legacy._app()
            with self.delivered():
                self.install(app, readiness=check)
                self.assertEqual((await self.asgi(app))[1], core.NodeHealthReadOutcome.UNHEALTHY)
                self.assertEqual(calls, [])
                async with app.router.lifespan_context(app):
                    self.assertEqual((await self.asgi(app, token=b"invalid"))[0], 401)
                    self.assertEqual(calls, [])
                    self.assertEqual((await self.asgi(app))[1], core.NodeHealthReadOutcome.HEALTHY)
                    self.assertEqual(calls, [1])
                self.assertEqual((await self.asgi(app))[1], core.NodeHealthReadOutcome.UNHEALTHY)
                self.assertEqual(calls, [1])
        asyncio.run(exercise())

    def server(self, *, name="CpkThreadingHTTPServer", **changes):
        server_type = getattr(stdlib_sdk, name, None)
        self.assertIsNotNone(server_type, "automatic stdlib wrapper is missing")
        server = server_type(("127.0.0.1", 0), http_fixtures.ApplicationHandler,
                             clock=lambda: 150, **changes)
        server.daemon_threads = False
        server.application_calls, server.application_logs = [], []
        return server

    def request(self, server, *, token=None):
        helper = http_fixtures.StdlibControlTests()
        helper.fixture = self.fixture
        status, body = helper.response(helper.request(server, token=token))
        if status == 200:
            return status, core.NodeHealthReadResultCodec(self.fixture.request, self.fixture.declaration).decode(json.loads(body)).outcome
        return status, body

    def test_stdlib_zero_callback_wrapper_serves_signed_baseline_and_preserves_application(self):
        for name in ("CpkHTTPServer", "CpkThreadingHTTPServer"):
            with self.subTest(host=name), self.delivered():
                server = self.server(name=name)
                thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
                try:
                    thread.start()
                    deadline = time.monotonic() + 3
                    while True:
                        status, outcome = self.request(server)
                        self.assertEqual(status, 200)
                        if outcome is core.NodeHealthReadOutcome.HEALTHY:
                            break
                        self.assertEqual(outcome, core.NodeHealthReadOutcome.UNHEALTHY)
                        self.assertLess(time.monotonic(), deadline)
                    self.assertEqual(self.request(server, token=b"invalid")[0], 401)
                    helper = http_fixtures.StdlibControlTests()
                    helper.fixture = self.fixture
                    raw = helper.request(server, target=b"/ordinary")
                    self.assertIn(b"201", raw.split(b"\r\n", 1)[0])
                    self.assertEqual(len(server.application_calls), 1)
                finally:
                    server.shutdown()
                    thread.join(3)
                    server.server_close()
                self.assertFalse(thread.is_alive())
                self.assertEqual(server.socket.fileno(), -1)

    def test_stdlib_shutdown_overrides_an_inflight_optional_ready_observation(self):
        entered, release = Event(), Event()
        def check():
            entered.set()
            if not release.wait(3):
                raise RuntimeError("test callback release timed out")
            return core.NodeHealthReadOutcome.HEALTHY
        with self.delivered():
            server = self.server(readiness=check)
            serving = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
            result = []
            reader = Thread(target=lambda: result.append(self.request(server)))
            try:
                serving.start()
                # A public stdlib hook witnesses entered service before optional observation.
                deadline = time.monotonic() + 3
                while not server.cpk_is_serving:
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(0.005)
                reader.start()
                self.assertTrue(entered.wait(2))
                server.shutdown()
                serving.join(2)
                self.assertFalse(server.cpk_is_serving)
                # A late loop hook must not resurrect readiness after shutdown.
                server.service_actions()
                self.assertFalse(server.cpk_is_serving)
                release.set()
                reader.join(2)
                self.assertEqual(result, [(200, core.NodeHealthReadOutcome.UNHEALTHY)])
            finally:
                release.set()
                if serving.is_alive():
                    server.shutdown()
                    serving.join(2)
                if reader.ident is not None:
                    reader.join(2)
                server.server_close()
            self.assertEqual(server.socket.fileno(), -1)

    def test_stdlib_installation_and_bind_failures_close_socket_before_return(self):
        with self.delivered(b"invalid"), patch.object(HTTPServer, "server_bind") as bind:
            self.refusal(self.server)
            bind.assert_not_called()
        captured = []
        original = HTTPServer.__init__
        def construct(server, *args, **kwargs):
            original(server, *args, **kwargs)
            captured.append(server.socket)
        with self.delivered(), patch.object(HTTPServer, "__init__", construct), \
                patch.object(HTTPServer, "server_bind") as bind:
            with self.assertRaises(ValueError):
                self.server(variables=(object(),))
            bind.assert_not_called()
        self.assertTrue(captured)
        self.assertTrue(all(connection.fileno() == -1 for connection in captured))
        captured.clear()
        failure = RuntimeError("bind failed")
        with self.delivered(), patch.object(HTTPServer, "__init__", construct), \
                patch.object(HTTPServer, "server_bind", side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                self.server()
            self.assertIs(caught.exception, failure)
        self.assertTrue(all(connection.fileno() == -1 for connection in captured))

    def test_stdlib_late_service_hook_cannot_override_concurrent_shutdown(self):
        entered, release, stopping = Event(), Event(), Event()
        observations = []
        original_shutdown = HTTPServer.shutdown
        def service_action(server):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("service hook release timed out")
        def shutdown(server):
            stopping.set()
            original_shutdown(server)
        with self.delivered(), patch.object(HTTPServer, "service_actions", service_action), \
                patch.object(HTTPServer, "shutdown", shutdown):
            server = self.server()
            original_action = server.service_actions
            def observed_action():
                original_action()
                observations.append(server.cpk_is_serving)
            server.service_actions = observed_action
            serving = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
            closing = Thread(target=server.shutdown)
            try:
                serving.start()
                self.assertTrue(entered.wait(2))
                closing.start()
                self.assertTrue(stopping.wait(2))
                release.set()
                closing.join(2)
                serving.join(2)
                self.assertEqual(observations, [False])
                self.assertFalse(server.cpk_is_serving)
                self.assertFalse(closing.is_alive())
                self.assertFalse(serving.is_alive())
            finally:
                release.set()
                if serving.is_alive() and closing.ident is None:
                    server.shutdown()
                serving.join(2)
                if closing.ident is not None:
                    closing.join(2)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
