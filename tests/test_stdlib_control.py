"""Owning in-container loopback witnesses for passive stdlib composition."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import socket
from threading import Event, Thread
import unittest

import control_plane_kit_core as core
from control_plane_kit_server_sdk.health import WorkloadNodeHealthReadDispatcher
from control_plane_kit_server_sdk.stdlib import install_cpk_control_routes
from tests import test_fastapi_control_routes as legacy
from tests import test_health_verification as credentials


class ApplicationHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 2

    def do_GET(self):
        self._application()

    def do_POST(self):
        self._application()

    def _application(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.server.application_calls.append((self.command, self.path, body))
        payload = b"application:" + body
        self.send_response(201)
        self.send_header("Content-Type", "application/x-original")
        self.send_header("X-Original", "retained")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        self.server.application_logs.append(format % args)


class StdlibControlTests(unittest.TestCase):
    def setUp(self):
        self.old = legacy.FastApiControlRouteTests()
        self.old.setUpClass()
        self.fixture = credentials.SignedHealthReadVerificationTests()
        self.fixture.setUp()
        self.calls = []
        self.outcome = core.NodeHealthReadOutcome.HEALTHY

    def observe(self):
        self.calls.append(1)
        return self.outcome

    def settings(self, *, declaration=None, target=None, callback=None, variables=(), command=None):
        declaration = self.fixture.declaration if declaration is None else declaration
        target = self.fixture.target if target is None else target
        dispatcher = None
        if declaration.profile is core.WorkloadNodeControlSurfaceDeclarationProfile.V2:
            dispatcher = WorkloadNodeHealthReadDispatcher(
                target=target, runtime_id=self.fixture.runtime, declaration=declaration,
                verifier=self.fixture.verifier(), liveness=self.observe,
                readiness=self.observe if callback is None else callback,
            )
        return dict(reserve_control_namespace=True, target=target, declaration=declaration,
                    variables=variables, command_verifier=command,
                    surface_read_verifier=self.old._surface_verifier(), health_dispatcher=dispatcher)

    def server(self, *, handler=ApplicationHandler, kind=ThreadingHTTPServer, address=("127.0.0.1", 0)):
        server = kind(address, handler, bind_and_activate=False)
        # Test-owned shutdown joins every request worker; callbacks remain bounded.
        server.daemon_threads = False
        server.application_calls = []
        server.application_logs = []
        return server

    @contextmanager
    def running(self, *, server=None, settings=None, install=True):
        server = self.server() if server is None else server
        thread = None
        try:
            if install:
                install_cpk_control_routes(server, **(self.settings() if settings is None else settings))
            server.server_bind()
            server.server_activate()
            thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
            thread.start()
            yield server, thread
        finally:
            if thread is not None:
                server.shutdown()  # Always outside the serving thread.
            server.server_close()
            if thread is not None:
                thread.join(3)
                self.assertFalse(thread.is_alive())
            self.assertEqual(server.socket.fileno(), -1)

    def wire(self, server, payload, *, eof=True):
        with socket.create_connection(server.server_address, timeout=2) as connection:
            connection.settimeout(2)
            connection.sendall(payload)
            if eof:
                connection.shutdown(socket.SHUT_WR)
            response = b""
            while True:
                try:
                    piece = connection.recv(4096)
                except ConnectionResetError:
                    break
                if not piece:
                    break
                response += piece
                self.assertLessEqual(len(response), 131072)
            return response

    def request(self, server, *, target=b"/__control/health/readiness", method=b"GET",
                token=None, headers=(), body=b"", version=b"HTTP/1.1", eof=True):
        token = self.fixture.token() if token is None else token
        head = method + b" " + target + b" " + version + b"\r\n"
        head += b"Host: loopback\r\nAuthorization: Bearer " + token + b"\r\n"
        head += b"".join(name + b": " + value + b"\r\n" for name, value in headers)
        return self.wire(server, head + b"\r\n" + body, eof=eof)

    def response(self, raw, *, head=False):
        header, body = raw.split(b"\r\n\r\n", 1)
        lines = header.split(b"\r\n")
        status = int(lines[0].split()[1])
        headers = dict(line.split(b": ", 1) for line in lines[1:])
        self.assertEqual(headers[b"Connection"], b"close")
        self.assertEqual(headers[b"Cache-Control"], b"no-store")
        self.assertEqual(len(body), 0 if head else int(headers[b"Content-Length"]))
        return status, body

    def test_installation_is_passive_atomic_and_rejects_unsupported_or_used_hosts(self):
        original_class = dict(ApplicationHandler.__dict__)
        for kind in (HTTPServer, ThreadingHTTPServer):
            server = self.server(kind=kind)
            try:
                prior = dict(vars(server))
                for change in ({"reserve_control_namespace": False}, {"surface_read_verifier": None},
                               {"command_verifier": self.old._command_verifier()}):
                    with self.assertRaises(ValueError) as caught:
                        install_cpk_control_routes(server, **{**self.settings(), **change})
                    self.assertIsNone(caught.exception.__context__)
                    self.assertIs(server.RequestHandlerClass, ApplicationHandler)
                install_cpk_control_routes(server, **self.settings())
                installed = server.RequestHandlerClass
                self.assertIsNot(installed, ApplicationHandler)
                for name, value in prior.items():
                    if name != "RequestHandlerClass":
                        self.assertIs(vars(server)[name], value)
                self.assertEqual(server.socket.getsockname()[1], 0)
                self.assertEqual(server.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN), 0)
                with self.assertRaises(ValueError):
                    install_cpk_control_routes(server, **self.settings())
                self.assertIs(server.RequestHandlerClass, installed)
            finally:
                server.server_close()
        self.assertEqual(dict(ApplicationHandler.__dict__), original_class)
        self.assertEqual(self.calls, [])
        variable = legacy.RecordingVariable("routing")
        server = self.server()
        try:
            settings = self.settings(declaration=legacy._declaration("routing"),
                                     variables=(variable,), command=self.old._command_verifier())
            with self.assertRaises(ValueError):
                install_cpk_control_routes(server, **{**settings, "reserve_control_namespace": False})
            self.assertEqual(variable.descriptor_calls, 0)
        finally:
            server.server_close()
        class CustomServer(ThreadingHTTPServer):
            pass
        class CustomHandler(ApplicationHandler):
            def parse_request(self):
                return True
        for options in ({"kind": CustomServer}, {"handler": CustomHandler}, {}):
            server = self.server(**options)
            try:
                if not options:
                    server.server_bind()
                with self.assertRaises(ValueError):
                    install_cpk_control_routes(server, **self.settings())
            finally:
                server.server_close()
            with self.assertRaises(ValueError):
                install_cpk_control_routes(server, **self.settings())

    def test_health_outcomes_static_authority_and_correlated_repeated_reads(self):
        with self.running() as (server, _):
            for kind in core.NodeHealthReadKind:
                for outcome in core.NodeHealthReadOutcome:
                    self.outcome = outcome
                    request = replace(self.fixture.request, kind=kind,
                                      request_id=f"stdlib-{kind.value}-{outcome.value}")
                    token = self.fixture.token(self.fixture.grant(request))
                    for _ in range(2):
                        status, body = self.response(self.request(
                            server, target=b"/__control/health/" + kind.value.encode(), token=token,
                            version=b"HTTP/1.0" if kind is core.NodeHealthReadKind.LIVENESS else b"HTTP/1.1"))
                        self.assertEqual(status, 200)
                        self.assertEqual(body, core.NodeHealthReadResult(
                            request, self.fixture.declaration, outcome).canonical_bytes())
            self.assertEqual(len(self.calls), 16)
            for kind in core.NodeControlSurfaceReadKind:
                request = legacy._surface_request(self.fixture.declaration, kind, target=self.fixture.target)
                token = legacy._surface_token(self.old.surface_private, request)
                status, body = self.response(self.request(server, token=token,
                                          target=b"/__control/" + kind.value.encode()))
                self.assertEqual(status, 200)
                codec = core.NodeControlSurfaceReadResultCodec(request, self.fixture.declaration)
                expected = codec.capabilities_result() if kind is core.NodeControlSurfaceReadKind.CAPABILITIES else codec.status_result(())
                self.assertEqual(body, expected.canonical_bytes())
                self.assertEqual(self.response(self.request(server, target=b"/__control/" + kind.value.encode()))[0], 401)
            self.assertEqual(len(self.calls), 16)
            self.assertEqual(server.application_calls, [])
            self.assertEqual(server.application_logs, [])

    def test_legacy_and_mixed_variable_behavior_reuses_authenticated_command_replay(self):
        for mixed in (False, True):
            variable = legacy.RecordingVariable("routing")
            declaration = legacy._declaration("routing")
            if mixed:
                declaration = replace(self.fixture.declaration, surface=replace(
                    self.fixture.declaration.surface, variables=declaration.surface.variables))
            with self.running(settings=self.settings(declaration=declaration,
                              variables=(variable,), command=self.old._command_verifier())) as (server, _):
                self.assertEqual(variable.descriptor_calls, 1)
                for operation in core.NodeControlOperation:
                    request = legacy._command_request(operation, target=self.fixture.target)
                    token = legacy._command_token(self.old.command_private, request)
                    body = legacy._json_bytes(request.descriptor()) if operation is core.NodeControlOperation.APPLY_COMMAND else b""
                    for _ in range(2):
                        status, _body = self.response(self.request(
                            server, token=token, method=b"POST" if body else b"GET", body=body,
                            target=b"/__control/variables/routing" + (b"/commands" if body else b""),
                            headers=((b"Content-Length", str(len(body)).encode()),)))
                        self.assertEqual(status, 200)
                self.assertEqual(variable.read_calls, 2)
                self.assertEqual(variable.apply_calls, 1)
                self.assertEqual(variable.descriptor_calls, 1)
                self.assertEqual(server.application_calls, [])

    def test_raw_denials_are_terminal_nonlogging_and_precede_all_callbacks(self):
        foreign = replace(self.fixture.request, runtime_id=replace(self.fixture.runtime, value="other"))
        nested = b"%5f%5fcontrol"
        for _ in range(17):
            nested = nested.replace(b"%", b"%25")
        targets = (
            b"//__control/health/readiness", b"/%5f%5fcontrol/health/readiness",
            b"/__control%2fhealth/readiness", b"/x/../__control/status",
            b"/__control/../application", b"/%5f%5fcontrol/../application",
            b"http://host/__control/status", b"/" + nested + b"/status",
            b"/__control/health/readiness/", b"/__control/health/readiness?",
            b"/__control/health/readiness#fragment", b"/__control/health/unknown",
        )
        with self.running() as (server, _):
            for target in targets:
                with self.subTest(target=target):
                    status, body = self.response(self.request(server, target=target))
                    self.assertIn(status, (400, 404))
                    self.assertNotIn(b"outcome", body)
            for token in (self.fixture.token(private=self.fixture.other_private),
                          self.fixture.token(self.fixture.grant(foreign)),
                          self.fixture.token(self.fixture.grant(expires_at=150))):
                self.assertEqual(self.response(self.request(server, token=token))[0], 401)
            self.assertEqual(self.response(self.wire(server,
                b"GET /__control/health/readiness HTTP/1.1\r\nHost: loopback\r\n\r\n"))[0], 401)
            self.assertEqual(self.response(self.wire(server,
                b"GET\xa0/__control/health/readiness HTTP/1.1\r\nHost: loopback\r\n\r\n"))[0], 401)
            self.assertEqual(self.response(self.request(server, target=b"/__control/" + b"x" * 1025))[0], 413)
            self.assertEqual(self.response(self.request(server,
                headers=tuple((b"X-Test", b"x") for _ in range(105))))[0], 413)
            cases = (
                (((b"Authorization", b"Bearer extra"),), 401),
                (((b"Content-Length", b"0"), (b"Content-Length", b"0")), 400),
                (((b"Content-Length", b"01"),), 400),
                (((b"Content-Length", b"1"),), 400),
                (((b"Content-Length", b"16385"),), 413),
                (((b"Transfer-Encoding", b"chunked"),), 400),
                (((b"Expect", b"100-continue"),), 400),
                (((b"X-Oversized", b"x" * 32769),), 413),
            )
            for headers, expected in cases:
                self.assertEqual(self.response(self.request(server, headers=headers, eof=False))[0], expected)
            for method in (b"POST", b"HEAD", b"UNSUPPORTED"):
                self.assertEqual(self.response(self.request(server, method=method), head=method == b"HEAD")[0], 405)
            for version in (b"HTTP/0.9", b"HTTP/2.0", b"HTTP/private-marker"):
                self.assertEqual(self.response(self.request(server, version=version))[0], 400)
            self.assertEqual(self.response(self.wire(server, b"GET /__control/health/readiness\r\n\r\n"))[0], 400)
            # Bytes after a declared bodyless control request never become an app request.
            self.assertEqual(self.response(self.request(server, token=b"invalid", body=(
                b"GET /ordinary HTTP/1.1\r\nHost: loopback\r\n\r\n")))[0], 401)
            self.assertEqual(self.calls, [])
            self.assertEqual(server.application_calls, [])
            self.assertEqual(server.application_logs, [])

    def test_application_payload_headers_expect_keepalive_and_legacy_behavior_are_preserved(self):
        with self.running() as (server, _):
            raw = self.wire(server, b"POST /ordinary HTTP/1.1\r\nHost: loopback\r\n"
                            b"Content-Length: 4\r\nExpect: 100-continue\r\n\r\nbody"
                            b"GET /__control-extra HTTP/1.1\r\nHost: loopback\r\nConnection: close\r\n\r\n")
            self.assertIn(b"100 Continue", raw)
            self.assertEqual(raw.count(b"201 Created"), 2)
            self.assertEqual(raw.count(b"X-Original: retained"), 2)
            self.assertIn(b"application:body", raw)
            self.assertEqual(server.application_calls, [("POST", "/ordinary", b"body"), ("GET", "/__control-extra", b"")])
            for target in (b"/__CONTROL/status", b"/app?next=/__control/status", b"/%70ublic"):
                raw = self.wire(server, b"GET " + target + b" HTTP/1.1\r\nHost: loopback\r\nConnection: close\r\n\r\n")
                self.assertIn(b"201 Created", raw)
                self.assertEqual(server.application_calls[-1][1], target.decode())
            raw = self.wire(server, b"GET /legacy\r\n\r\n")
            self.assertEqual(raw, b"application:")
            encoded_public = b"%61pp"
            for _ in range(15):
                encoded_public = encoded_public.replace(b"%", b"%25")
            target = b"/" + encoded_public
            self.assertIn(b"201 Created", self.wire(server,
                b"GET " + target + b" HTTP/1.1\r\nHost: loopback\r\nConnection: close\r\n\r\n"))
            self.assertEqual(server.application_calls[-1][1], target.decode())
            prior_calls = len(server.application_calls)
            exhausted = b"/" + encoded_public.replace(b"%", b"%25")
            self.assertEqual(self.response(self.request(server, target=exhausted))[0], 400)
            self.assertEqual(len(server.application_calls), prior_calls)
            self.assertEqual(self.calls, [])

    def test_cross_server_binding_and_callback_errors_do_not_leak_or_retry(self):
        def fail():
            self.calls.append(1)
            raise RuntimeError("callback-private-marker")
        with self.running(settings=self.settings(callback=fail)) as (first, _):
            status, body = self.response(self.request(first))
            self.assertEqual(status, 500)
            self.assertNotIn(b"callback-private-marker", body)
            second = self.server()
            second.RequestHandlerClass = first.RequestHandlerClass
            with self.running(server=second, install=False) as (other, _):
                self.assertEqual(self.response(self.request(other))[0], 403)
                self.assertEqual(other.application_calls, [])
            self.assertEqual(self.calls, [1])

    def test_apply_body_denials_and_legitimate_servers_have_independent_context_and_replay(self):
        first_variable, second_variable = legacy.RecordingVariable("routing"), legacy.RecordingVariable("routing")
        declaration = legacy._declaration("routing")
        other_target = replace(self.fixture.target, node_id=replace(self.fixture.target.node_id, value="other"))
        first_settings = self.settings(declaration=declaration, variables=(first_variable,), command=self.old._command_verifier())
        second_settings = self.settings(declaration=declaration, target=other_target,
                                        variables=(second_variable,), command=self.old._command_verifier())
        first_request = legacy._command_request(core.NodeControlOperation.APPLY_COMMAND, target=self.fixture.target)
        other_request = legacy._command_request(core.NodeControlOperation.APPLY_COMMAND, target=other_target)
        first_token = legacy._command_token(self.old.command_private, first_request)
        first_body = legacy._json_bytes(first_request.descriptor())
        with self.running(settings=first_settings) as (first, _), self.running(settings=second_settings) as (second, _):
            for headers, body, expected in (
                (((b"Content-Length", b"3"),), b"x", 400),
                (((b"Content-Length", b"16385"),), b"", 413),
                (((b"Content-Length", b"8"),), b"not-json", 401),
            ):
                status, _body = self.response(self.request(first, method=b"POST",
                    target=b"/__control/variables/routing/commands", token=first_token, headers=headers, body=body))
                self.assertEqual(status, expected)
            self.assertEqual(first_variable.apply_calls, 0)
            self.assertEqual(self.response(self.request(second, method=b"POST",
                target=b"/__control/variables/routing/commands", token=first_token, body=first_body,
                headers=((b"Content-Length", str(len(first_body)).encode()),)))[0], 403)
            self.assertEqual(second_variable.apply_calls, 0)
            for server, request in ((first, first_request), (second, other_request)):
                body = legacy._json_bytes(request.descriptor())
                for _ in range(2):
                    self.assertEqual(self.response(self.request(server, method=b"POST",
                        target=b"/__control/variables/routing/commands",
                        token=legacy._command_token(self.old.command_private, request), body=body,
                        headers=((b"Content-Length", str(len(body)).encode()),)))[0], 200)
            self.assertEqual((first_variable.apply_calls, second_variable.apply_calls), (1, 1))

    def test_disconnected_admitted_callback_completes_once_without_retry(self):
        entered, release = Event(), Event()
        def ready():
            self.calls.append(1)
            entered.set()
            if not release.wait(2):
                raise RuntimeError("test callback release timed out")
            return core.NodeHealthReadOutcome.HEALTHY
        with self.running(settings=self.settings(callback=ready)) as (server, _):
            try:
                with socket.create_connection(server.server_address, timeout=2) as connection:
                    connection.sendall(b"GET /__control/health/readiness HTTP/1.1\r\n"
                                       b"Host: loopback\r\nAuthorization: Bearer " + self.fixture.token() + b"\r\n\r\n")
                    self.assertTrue(entered.wait(1))
                    connection.shutdown(socket.SHUT_RDWR)
            finally:
                release.set()
        # The test host's server_close joins non-daemon workers after release.
        self.assertEqual(self.calls, [1])

    def test_product_owned_bind_failure_shutdown_and_inflight_completion_cleanup(self):
        entered, release = Event(), Event()
        def ready():
            self.calls.append(1)
            entered.set()
            if not release.wait(2):
                raise RuntimeError("test callback release timed out")
            return core.NodeHealthReadOutcome.HEALTHY
        with self.running(settings=self.settings(callback=ready)) as (server, serving):
            address = server.server_address
            contender = self.server(address=address)
            try:
                install_cpk_control_routes(contender, **self.settings())
                with self.assertRaises(OSError):
                    contender.server_bind()
            finally:
                contender.server_close()
            self.assertEqual(contender.socket.fileno(), -1)
            with ThreadPoolExecutor(max_workers=1) as client:
                pending = client.submit(self.request, server)
                try:
                    self.assertTrue(entered.wait(1))
                    server.shutdown()
                    serving.join(2)
                    self.assertFalse(serving.is_alive())
                finally:
                    release.set()
                self.assertEqual(self.response(pending.result(timeout=3))[0], 200)
            self.assertEqual(self.calls, [1])
        with self.assertRaises(OSError):
            with socket.create_connection(address, timeout=0.2):
                pass


if __name__ == "__main__":
    unittest.main()
