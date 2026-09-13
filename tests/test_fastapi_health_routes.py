"""Real signed ASGI requests through the one public installer; no listener."""
import asyncio
from dataclasses import replace
import json
from threading import Event, get_ident
import unittest

import control_plane_kit_core as core
from control_plane_kit_server_sdk.fastapi import install_cpk_control_routes
from control_plane_kit_server_sdk.health import WorkloadNodeHealthReadDispatcher
from tests import test_fastapi_control_routes as legacy
from tests import test_health_verification as credentials


_DEFAULT_RAW_PATH = object()


class FastApiHealthRouteTests(unittest.TestCase):
    def setUp(self):
        self.fixture = credentials.SignedHealthReadVerificationTests()
        self.fixture.setUp()
        self.old = legacy.FastApiControlRouteTests()
        self.old.setUpClass()
        self.calls = []
        self.outcome = core.NodeHealthReadOutcome.HEALTHY

    def observe(self):
        self.calls.append(get_ident())
        return self.outcome

    def dispatcher(self, **changes):
        return WorkloadNodeHealthReadDispatcher(**{
            "target": self.fixture.target, "runtime_id": self.fixture.runtime,
            "declaration": self.fixture.declaration, "verifier": self.fixture.verifier(),
            "liveness": self.observe, "readiness": self.observe, **changes,
        })

    def install(self, *, dispatcher=None, app=None, **changes):
        app = self.old._app() if app is None else app
        dispatcher = self.dispatcher() if dispatcher is None else dispatcher
        install_cpk_control_routes(app, **{
            "target": dispatcher.target, "declaration": dispatcher.declaration,
            "surface_read_verifier": self.old._surface_verifier(),
            "health_dispatcher": dispatcher, **changes,
        })
        return app

    async def asgi(self, app, *, method="GET", path="/__control/health/readiness",
                   token=None, headers=None, chunks=(b"",), query=b"", raw_path=_DEFAULT_RAW_PATH):
        messages = [dict(type="http.request", body=chunk, more_body=index < len(chunks)-1)
                    for index, chunk in enumerate(chunks)]
        sent = []
        async def receive():
            return messages.pop(0) if messages else {"type": "http.disconnect"}
        async def send(message):
            sent.append(message)
        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": method, "scheme": "http", "path": path,
            "raw_path": path.encode("ascii") if raw_path is _DEFAULT_RAW_PATH else raw_path,
            "query_string": query,
            "headers": [(b"authorization", b"Bearer " + (self.fixture.token() if token is None else token))]
                       if headers is None else headers,
            "client": ("test", 123), "server": ("test", 80), "root_path": "",
        }
        await app(scope, receive, send)
        start = next(message for message in sent if message["type"] == "http.response.start")
        body = b"".join(message.get("body", b"") for message in sent
                        if message["type"] == "http.response.body")
        return start["status"], dict(start["headers"]), body

    def test_health_only_and_mixed_installation_preserve_application_and_static_authority(self):
        for mixed in (False, True):
            with self.subTest(mixed=mixed):
                prior_calls = tuple(self.calls)
                declaration = self.fixture.declaration
                variables = ()
                arguments = {}
                if mixed:
                    declaration = replace(declaration, surface=replace(
                        declaration.surface, variables=(legacy._descriptor("routing"), legacy._descriptor("other")),
                    ))
                    variables = (legacy.RecordingVariable("routing"),)
                    arguments = {"variables": variables, "command_verifier": self.old._command_verifier()}
                app = self.old._app()
                prior = tuple(app.router.routes)
                self.install(app=app, dispatcher=self.dispatcher(declaration=declaration), **arguments)
                self.assertEqual(tuple(app.router.routes[:len(prior)]), prior)
                installed = app.router.routes[len(prior):]
                self.assertEqual(len(installed), 5 if mixed else 3)
                self.assertTrue(all(not route.include_in_schema for route in installed))
                self.assertEqual(tuple(self.calls), prior_calls)
                request = replace(self.fixture.request, declaration_identity=declaration.identity())
                status, headers, body = asyncio.run(self.asgi(app, token=self.fixture.token(self.fixture.grant(request))))
                self.assertEqual(status, 200)
                self.assertEqual(headers[b"cache-control"], b"no-store")
                self.assertEqual(core.NodeHealthReadResultCodec(request, declaration).decode(json.loads(body)).outcome,
                                 core.NodeHealthReadOutcome.HEALTHY)
                before = len(self.calls)
                for kind in core.NodeControlSurfaceReadKind:
                    surface_request = legacy._surface_request(declaration, kind, target=self.fixture.target)
                    token = legacy._surface_token(self.old.surface_private, surface_request)
                    path = "/__control/" + kind.value
                    status, _, body = asyncio.run(self.asgi(app, path=path, token=token))
                    self.assertEqual(status, 200)
                    codec = core.NodeControlSurfaceReadResultCodec(surface_request, declaration)
                    expected = codec.capabilities_result() if kind is core.NodeControlSurfaceReadKind.CAPABILITIES else codec.status_result(
                        tuple(variable.descriptor().variable_name for variable in variables),
                    )
                    self.assertEqual(body, expected.canonical_bytes())
                    denied, _, _ = asyncio.run(self.asgi(app, path=path))
                    self.assertEqual(denied, 401)  # A health credential is not static authority.
                self.assertEqual(len(self.calls), before)
                status, _, body = asyncio.run(self.asgi(app, path="/ordinary", headers=[]))
                self.assertEqual((status, json.loads(body)), (200, {"message": "ordinary"}))
                if mixed:
                    command = legacy._command_request(core.NodeControlOperation.APPLY_COMMAND, target=self.fixture.target)
                    for _ in range(2):
                        code, _ = asyncio.run(self.old._command_call(app, command))
                        self.assertEqual(code, 200)
                    self.assertEqual(variables[0].apply_calls, 1)
                else:
                    status, _, _ = asyncio.run(self.asgi(app, path="/__control/variables/routing"))
                    self.assertEqual(status, 404)

    def test_configuration_and_collisions_fail_before_host_route_publication(self):
        dispatcher = self.dispatcher()
        old_declaration = legacy._declaration("routing")
        cases = (
            {"health_dispatcher": None}, {"health_dispatcher": object()},
            {"command_verifier": self.old._command_verifier()},
            {"variables": (legacy.RecordingVariable("routing"),)},
            {"surface_read_verifier": None}, {"declaration": old_declaration},
            {"target": replace(self.fixture.target, node_id=replace(self.fixture.target.node_id, value="other"))},
        )
        for change in cases:
            app = self.old._app()
            prior = app.router.routes
            original = tuple(prior)
            with self.subTest(field=tuple(change)), self.assertRaises(ValueError):
                install_cpk_control_routes(app, **{
                    "target": dispatcher.target, "declaration": dispatcher.declaration,
                    "surface_read_verifier": self.old._surface_verifier(),
                    "health_dispatcher": dispatcher, **change,
                })
            self.assertIs(app.router.routes, prior)
            self.assertEqual(tuple(app.router.routes), original)
        for mode in ("legacy", "health", "mixed"):
            app = self.old._app()
            app.add_api_route("/__control/collision", lambda: {})
            prior = app.router.routes
            arguments = dict(target=dispatcher.target, declaration=dispatcher.declaration,
                             health_dispatcher=dispatcher, surface_read_verifier=self.old._surface_verifier())
            if mode == "legacy":
                arguments.update(declaration=old_declaration, health_dispatcher=None,
                                 command_verifier=self.old._command_verifier())
            elif mode == "mixed":
                declaration = replace(dispatcher.declaration, surface=replace(
                    dispatcher.declaration.surface, variables=(legacy._descriptor("routing"),),
                ))
                arguments.update(declaration=declaration, health_dispatcher=self.dispatcher(declaration=declaration),
                                 command_verifier=self.old._command_verifier())
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "collides"):
                install_cpk_control_routes(app, **arguments)
            self.assertIs(app.router.routes, prior)
        app = self.install()
        prior = app.router.routes
        with self.assertRaisesRegex(ValueError, "already installed"):
            self.install(app=app)
        self.assertIs(app.router.routes, prior)
        self.assertEqual(self.calls, [])

    def test_real_signed_denials_and_exact_http_framing_invoke_zero_callbacks(self):
        app = self.install()
        request = self.fixture.request
        foreign = replace(request, target=replace(request.target, node_id=replace(request.target.node_id, value="other")))
        authorization = (b"authorization", b"Bearer " + self.fixture.token())
        static_request = legacy._surface_request(self.fixture.declaration, core.NodeControlSurfaceReadKind.STATUS,
                                                  target=self.fixture.target)
        cases = (
            ({"token": self.fixture.token(private=self.fixture.other_private)}, 401),
            ({"token": self.fixture.token(self.fixture.grant(foreign))}, 401),
            ({"token": self.fixture.token(self.fixture.grant(expires_at=150))}, 401),
            ({"token": legacy._surface_token(self.old.surface_private, static_request)}, 401),
            ({"path": "/__control/health/liveness"}, 401),
            ({"headers": [authorization, authorization]}, 401),
            ({"headers": []}, 401),
            ({"headers": [(b"x-test", b"x" * 32769)]}, 413),
            ({"query": b"runtime_id=other"}, 400),
            ({"query": b"x" * 1025}, 413),
            ({"chunks": (b"", b"private-body")}, 400),
            ({"chunks": (b"x" * 16385,)}, 413),
            ({"raw_path": b"/__control/health/%72eadiness"}, 400),
            ({"raw_path": b"/__control/health/readiness/"}, 400),
            ({"raw_path": None}, 400),
            ({"raw_path": b"x" * 1025}, 413),
            ({"path": "/__control/health/status"}, 404),
        )
        for changes, expected in cases:
            with self.subTest(changes=tuple(changes)):
                status, headers, body = asyncio.run(self.asgi(app, **changes))
                self.assertEqual(status, expected)
                self.assertEqual(headers[b"cache-control"], b"no-store")
                self.assertLess(len(body), 128)
                self.assertNotIn(b"outcome", body)
                self.assertNotIn(b"private-body", body)
                self.assertNotIn(b"Bearer", body)
        for changes in ({"method": "HEAD"}, {"path": "/__control/health/readiness/"}):
            status, _, _ = asyncio.run(self.asgi(app, **changes))
            self.assertIn(status, (307, 404, 405))
        self.assertEqual(self.calls, [])
        # Forwarded locality never overrides independently captured context.
        token = self.fixture.token(self.fixture.grant(foreign))
        status, _, _ = asyncio.run(self.asgi(app, headers=[
            (b"authorization", b"Bearer " + token), (b"x-runtime-id", self.fixture.runtime.value.encode()),
        ]))
        self.assertEqual(status, 401)
        self.assertEqual(self.calls, [])

    def test_outcomes_and_new_observation_correlation_are_core_results_without_cache(self):
        app = self.install()
        for kind in core.NodeHealthReadKind:
            for outcome in core.NodeHealthReadOutcome:
                self.outcome = outcome
                request = replace(self.fixture.request, kind=kind, request_id=f"health-{kind.value}-{outcome.value}")
                token = self.fixture.token(self.fixture.grant(request))
                path = "/__control/health/" + kind.value
                for _ in range(2):
                    status, headers, body = asyncio.run(self.asgi(app, path=path, token=token))
                    self.assertEqual(status, 200)
                    self.assertEqual(headers[b"cache-control"], b"no-store")
                    expected = core.NodeHealthReadResult(request, self.fixture.declaration, outcome)
                    self.assertEqual(body, expected.canonical_bytes())
                    self.assertLessEqual(len(body), 446)
        self.assertEqual(len(self.calls), 16)

    def test_bad_callback_is_fixed_nonsemantic_500_and_apps_are_isolated(self):
        def fail():
            self.calls.append(get_ident())
            raise RuntimeError("authorization: Bearer private-callback-marker")
        for callback in (fail, lambda: "healthy"):
            app = self.install(dispatcher=self.dispatcher(readiness=callback))
            status, headers, body = asyncio.run(self.asgi(app))
            self.assertEqual(status, 500)
            self.assertEqual(headers[b"cache-control"], b"no-store")
            self.assertEqual(body, b'{"code":"node-health.internal-failure"}')
        other_calls = []
        other_target = replace(self.fixture.target, node_id=replace(self.fixture.target.node_id, value="other"))
        app = self.install(dispatcher=self.dispatcher(target=other_target,
                           readiness=lambda: other_calls.append(1) or core.NodeHealthReadOutcome.UNHEALTHY))
        before = len(self.calls)
        self.assertEqual(asyncio.run(self.asgi(app))[0], 401)
        self.assertEqual(other_calls, [])
        request = replace(self.fixture.request, target=other_target)
        self.assertEqual(asyncio.run(self.asgi(app, token=self.fixture.token(self.fixture.grant(request))))[0], 200)
        self.assertEqual(other_calls, [1])
        self.assertEqual(len(self.calls), before)

    def test_admission_callback_and_result_work_do_not_block_the_event_loop(self):
        entered, release = Event(), Event()
        clock_threads = []
        def clock():
            clock_threads.append(get_ident())
            return 150
        def ready():
            self.calls.append(get_ident())
            entered.set()
            if not release.wait(3):
                raise RuntimeError("health callback test was not released")
            return core.NodeHealthReadOutcome.HEALTHY
        app = self.install(dispatcher=self.dispatcher(readiness=ready, verifier=self.fixture.verifier(clock=clock)))
        async def exercise():
            event_loop_thread = get_ident()
            pending = asyncio.create_task(self.asgi(app))
            try:
                for _ in range(100):
                    if entered.is_set():
                        break
                    await asyncio.sleep(0.01)
                self.assertTrue(entered.is_set())
                self.assertEqual(clock_threads, self.calls)
                self.assertNotEqual(self.calls[0], event_loop_thread)
            finally:
                release.set()
            return await asyncio.wait_for(pending, 3)
        self.assertEqual(asyncio.run(exercise())[0], 200)


if __name__ == "__main__":
    unittest.main()
