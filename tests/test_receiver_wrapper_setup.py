"""Receiver-only common setup through real SDK host entrypoints (L1–L3/L8)."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
import json
from threading import Thread
import time
import unittest

import control_plane_kit_core as core
from control_plane_kit_core.wrapper_configuration import (
    WorkloadNodeControlConfiguration, WorkloadNodeControlConfigurationCodec,
)
from control_plane_kit_server_sdk import fastapi as sdk_fastapi, stdlib as sdk_stdlib
from control_plane_kit_server_sdk.wrapper import load_wrapper_configuration, WrapperSetupError
from tests.receiver_fixtures import ReceiverFixture
from tests import test_fastapi_control_routes as application
from tests import test_fastapi_health_routes as asgi
from tests import test_stdlib_control as http


class ReceiverWrapperSetupTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ReceiverFixture()
        self.assertEqual(core.ReceiverNodeControlConfigurationCodec().decode_bytes(self.fixture.encoded),
                         self.fixture.configuration)
        request = self.fixture.health_request()
        self.assertEqual(core.ReceiverHealthReadRequestCodec().decode(request.descriptor()), request)
        _, grant = self.fixture.grant(request)
        self.assertTrue(core.verify_workload_receiver_health_read_grant(grant, request,
            expected_target=self.fixture.target, expected_declaration=self.fixture.declaration,
            expected_kind=request.kind, expected_issuer=grant.issuer, expected_key_id=grant.key_id,
            expected_audience=grant.audience, now=150).is_accepted)

    def install(self, app, **options):
        try:
            sdk_fastapi.install_cpk_wrapper(app, configuration=self.fixture.configuration,
                                           clock=lambda: 150, **options)
        except WrapperSetupError:
            self.fail("SDK setup refuses the valid accepted Core receiver configuration")

    async def read(self, app, request, **options):
        helper = asgi.FastApiHealthRouteTests()
        return await helper.asgi(app, token=self.fixture.token(request), **options)

    def test_loader_reads_receiver_configuration_and_refuses_historical_or_mixed_profile(self):
        with self.fixture.delivered():
            try:
                actual = load_wrapper_configuration()
            except WrapperSetupError:
                self.fail("SDK file loader does not adopt the valid Core receiver configuration")
            self.assertEqual(actual, self.fixture.configuration)
        document = json.loads(self.fixture.encoded)
        for change in ({"profile": "workload-node-control-configuration.v1"},
                       {"profile": "workload-node-control-configuration.v9"},
                       {"runtime_id": "runtime-a"}):
            with self.subTest(change=tuple(change)), self.fixture.delivered(json.dumps(document | change).encode()):
                with self.assertRaises(WrapperSetupError):
                    load_wrapper_configuration()
        historical_target = core.NodeControlTarget(
            self.fixture.target.workspace_id,
            core.NodeControlGraphReference(core.NodeControlGraphReferenceRole.GRAPH_REVISION, "graph-a"),
            self.fixture.target.node_id, self.fixture.target.provider_socket_name)
        historical = WorkloadNodeControlConfiguration(
            historical_target, self.fixture.target.runtime_id,
            self.fixture.declaration, self.fixture.configuration.verifiers)
        historical_codec = WorkloadNodeControlConfigurationCodec()
        raw = historical_codec.encode_bytes(historical)
        self.assertEqual(historical_codec.decode_bytes(raw), historical)
        with self.fixture.delivered(raw), self.assertRaises(WrapperSetupError):
            load_wrapper_configuration()
        app = application.FastApiControlRouteTests()._app()
        prior = app.router.routes
        with self.assertRaises(WrapperSetupError):
            sdk_fastapi.install_cpk_wrapper(app, configuration=historical)
        self.assertIs(app.router.routes, prior)

    def test_same_installed_receiver_accepts_two_contexts_with_exact_health_results(self):
        async def exercise():
            app = application.FastApiControlRouteTests()._app()
            self.install(app)
            async with app.router.lifespan_context(app):
                for suffix in ("a", "b"):
                    request = self.fixture.health_request(context=core.NodeControlAuthorityContext(
                        "graph-" + suffix, "projection-" + suffix), request_id="health-" + suffix)
                    status, _, body = await self.read(app, request)
                    self.assertEqual(status, 200)
                    result = core.ReceiverHealthReadResultCodec(request, self.fixture.declaration).decode(json.loads(body))
                    self.assertEqual(result.request, request)
                    self.assertEqual(result.outcome, core.NodeHealthReadOutcome.HEALTHY)
                    self.assertEqual(json.loads(body)["request_digest"], request.canonical_digest().value)
                for name in ("workspace_id", "runtime_id", "node_id", "provider_socket_name", "receiver_id"):
                    value = getattr(self.fixture.target, name)
                    foreign = replace(self.fixture.target, **{name: "b" * 32 if name == "receiver_id"
                                      else replace(value, value="foreign")})
                    request = self.fixture.health_request(target=foreign)
                    status, _, body = await self.read(app, request)
                    self.assertEqual(status, 401)
                    self.assertNotIn(b"outcome", body)
        asyncio.run(exercise())

    def test_restart_reloads_same_identity_and_preserves_application_lifespan(self):
        async def exercise():
            events = []
            state = {"application": "retained"}
            @asynccontextmanager
            async def lifespan(app):
                events.append("start")
                try:
                    yield state
                finally:
                    events.append("stop")
            for _ in range(2):
                app = application.FastApiControlRouteTests()._app()
                app.router.lifespan_context = lifespan
                with self.fixture.delivered() as path:
                    try:
                        sdk_fastapi.install_cpk_wrapper(app, clock=lambda: 150)
                    except WrapperSetupError:
                        self.fail("SDK host cannot reconstruct the configured receiver on startup")
                    path.chmod(0o644)
                    path.write_bytes(b"changed-after-startup")
                    path.chmod(0o444)
                    request = self.fixture.health_request()
                    async with app.router.lifespan_context(app) as actual:
                        self.assertIs(actual, state)
                        self.assertEqual((await self.read(app, request))[0], 200)
                        code, _, body = await self.read(app, request, path="/ordinary", headers=[])
                        self.assertEqual((code, json.loads(body)), (200, {"message": "ordinary"}))
                    _, _, body = await self.read(app, request)
                    result = core.ReceiverHealthReadResultCodec(request, self.fixture.declaration).decode(json.loads(body))
                    self.assertEqual(result.outcome, core.NodeHealthReadOutcome.UNHEALTHY)
            self.assertEqual(events, ["start", "stop", "start", "stop"])
        asyncio.run(exercise())

    def test_both_stdlib_hosts_use_receiver_configuration_and_preserve_application(self):
        for server_type in (sdk_stdlib.CpkHTTPServer, sdk_stdlib.CpkThreadingHTTPServer):
            with self.subTest(server=server_type.__name__):
                try:
                    server = server_type(("127.0.0.1", 0), http.ApplicationHandler,
                        configuration=self.fixture.configuration, clock=lambda: 150)
                except WrapperSetupError:
                    self.fail("SDK stdlib setup refuses the valid Core receiver configuration")
                server.daemon_threads = False
                server.application_calls, server.application_logs = [], []
                thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
                helper = http.StdlibControlTests()
                try:
                    thread.start()
                    deadline = time.monotonic() + 3
                    while not server.cpk_is_serving:
                        self.assertLess(time.monotonic(), deadline)
                        time.sleep(0.005)
                    for suffix in ("a", "b"):
                        request = self.fixture.health_request(context=core.NodeControlAuthorityContext(
                            "graph-" + suffix, "projection-" + suffix))
                        code, body = helper.response(helper.request(server, token=self.fixture.token(request)))
                        self.assertEqual(code, 200)
                        result = core.ReceiverHealthReadResultCodec(request, self.fixture.declaration).decode(json.loads(body))
                        self.assertEqual(result.outcome, core.NodeHealthReadOutcome.HEALTHY)
                    code, _ = helper.response(helper.request(server, token=b"invalid"))
                    self.assertEqual(code, 401)
                    raw = helper.request(server, target=b"/ordinary", token=b"not-used")
                    self.assertIn(b"201", raw.split(b"\r\n", 1)[0])
                    self.assertEqual(len(server.application_calls), 1)
                finally:
                    server.shutdown()
                    thread.join(3)
                    server.server_close()
                self.assertFalse(thread.is_alive())
                self.assertEqual(server.socket.fileno(), -1)
