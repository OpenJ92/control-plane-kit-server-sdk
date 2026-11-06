"""Signed installed HTTP samples through actual maintained SDK entrypoints."""
import asyncio
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
import unittest

from cryptography.hazmat.primitives.asymmetric import ed25519
import control_plane_kit_core as core
from control_plane_kit_core.algebra import ProviderSocket
from control_plane_kit_core.products import ProviderRuntimePort
from control_plane_kit_core.types import Protocol
from control_plane_kit_core.verification import HttpCheck, VerificationContract, VerificationPolicy, VerificationOutcome
from control_plane_kit_core.http_verification_samples import (
    HttpVerificationSampleRequest, HttpVerificationSampleGrant,
    HttpVerificationSampleResultCodec, http_verification_check_digest,
)
from control_plane_kit_core.http_verification_sample_installation import (
    HttpVerificationSampleReceiverBinding, HttpVerificationSampleReceiverConfiguration,
    HttpVerificationSampleVerifierConfiguration, HttpVerificationSampleCheckBinding,
)
from control_plane_kit_server_sdk import fastapi as sdk_fastapi
from tests.receiver_fixtures import ReceiverFixture
from tests import test_verification as signed
from tests import test_fastapi_health_routes as asgi
from tests import test_fastapi_control_routes as application


class SampleFixture:
    def __init__(self, port, *, path="/ready", cap=16, timeout=1):
        self.receiver = ReceiverFixture()
        self.private = ed25519.Ed25519PrivateKey.generate()
        self.key = core.DelegationPublicKey("sample-key", core.DelegationKeyAlgorithm.ED25519,
                                          signed._public_pem(self.private))
        self.check = HttpCheck(check_id="ready", provider_socket="control", path=path,
            policy=VerificationPolicy(timeout_seconds=timeout, maximum_attempts=3,
                                      maximum_evidence_bytes=cap))
        self.binding = self.bind()
        self.binding = replace(self.binding, provider_ports=(ProviderRuntimePort("control", port),))
        target = self.receiver.target
        self.request = HttpVerificationSampleRequest(target=target,
            authority_context=self.receiver.context,
            declaration_identity=self.receiver.declaration.identity().value,
            gateway_target=replace(target, receiver_id="b" * 32,
                                   node_id=replace(target.node_id, value="gateway")),
            route_id="route-a", run_id="run-a", activity_id="activity-a", outer_attempt=1,
            effect_id="effect-a", request_fingerprint="c" * 64, check_id="ready",
            check_digest=http_verification_check_digest(self.check), sample_ordinal=1,
            request_id="sample-a")

    def bind(self):
        receiver = self.receiver.configuration
        configuration = HttpVerificationSampleReceiverConfiguration(receiver.target,
            receiver.declaration.identity().value,
            HttpVerificationSampleVerifierConfiguration(
                core.DelegationKeyPurpose.WORKLOAD_HTTP_VERIFICATION_SAMPLE, "sample-controller", (self.key,)),
            (HttpVerificationSampleCheckBinding(self.check.check_id,
                                               http_verification_check_digest(self.check)),))
        return HttpVerificationSampleReceiverBinding(configuration, receiver,
            VerificationContract((self.check,)), (ProviderSocket("control", Protocol.HTTP),),
            (ProviderRuntimePort("control", 8080),))

    def token(self, *, request=None, purpose=None, private=None, expires_at=160, **outer):
        grant = HttpVerificationSampleGrant(request=self.request if request is None else request,
            purpose=core.DelegationKeyPurpose.WORKLOAD_HTTP_VERIFICATION_SAMPLE if purpose is None else purpose,
            issuer="sample-controller", key_id=self.key.key_id,
            audience=self.binding.audience, issued_at=145, not_before=145,
            expires_at=expires_at, jti="sample-jti")
        document = dict(iss=grant.issuer, aud=grant.audience, iat=grant.issued_at,
            nbf=grant.not_before, exp=grant.expires_at, jti=grant.jti,
            workload_http_verification_sample=grant.descriptor()) | outer
        return signed._signed_compact(self.private if private is None else private,
            header_bytes=signed._json_value(dict(alg="EdDSA", kid=grant.key_id,
                typ="CPK-WORKLOAD-HTTP-VERIFICATION-SAMPLE+JWT")),
            payload_bytes=signed._json_value(document))


@contextmanager
def service(*, status=200, body=b"ready"):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, tuple(self.headers.items())))
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            return None
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = False
    thread = Thread(target=server.serve_forever, kwargs=dict(poll_interval=0.01))
    thread.start()
    try:
        yield server.server_port, requests
    finally:
        server.shutdown()
        thread.join(3)
        server.server_close()


class _SampleRouteHelpers:
    def install(self, fixture, **options):
        app = application.FastApiControlRouteTests()._app()
        try:
            sdk_fastapi.install_cpk_wrapper(app, configuration=fixture.receiver.configuration,
                clock=lambda: 150, http_sample_clock=lambda: 150, http_verification_binding=fixture.binding, **options)
        except (TypeError, ValueError):
            self.fail("SDK wrapper refuses an independently installed HTTP sample binding")
        return app

    def read(self, app, fixture, token=None, **options):
        helper = asgi.FastApiHealthRouteTests()
        return asyncio.run(helper.asgi(app, path="/__control/verification/http",
            token=fixture.token() if token is None else token, **options))


class HttpSampleRouteTests(_SampleRouteHelpers, unittest.TestCase):
    def test_signed_sample_uses_installed_local_check_and_correlated_result(self):
        with service() as (port, requests):
            fixture = SampleFixture(port)
            app = self.install(fixture)
            status, headers, body = self.read(app, fixture)
            self.assertEqual(status, 200)
            self.assertEqual(headers[b"cache-control"], b"no-store")
            result = HttpVerificationSampleResultCodec(fixture.request, fixture.check).decode(json.loads(body))
            self.assertEqual(result.outcome, VerificationOutcome.PASSED)
            self.assertEqual((result.evidence.status_code, result.evidence.response_bytes), (200, 5))
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0][0], "/ready")
            self.assertFalse(any(name.lower() == "authorization" for name, _ in requests[0][1]))
            self.assertNotIn(b"ready", body)

    def test_service_failures_and_observed_overflow_remain_bounded_service_evidence(self):
        for status, body, outcome, count in (
            (500, b"failed", VerificationOutcome.FAILED, 6),
            (302, b"redirect", VerificationOutcome.FAILED, 8),
            (200, b"x" * 16, VerificationOutcome.PASSED, 16),
            (200, b"x" * 17, VerificationOutcome.MALFORMED, 16),
        ):
            with self.subTest(status=status, count=len(body)), service(status=status, body=body) as (port, requests):
                fixture = SampleFixture(port)
                app = self.install(fixture)
                code, _, encoded = self.read(app, fixture)
                self.assertEqual(code, 200)
                result = HttpVerificationSampleResultCodec(fixture.request, fixture.check).decode(json.loads(encoded))
                self.assertEqual(result.outcome, outcome)
                self.assertEqual((result.evidence.status_code, result.evidence.response_bytes), (status, count))
                self.assertEqual(len(requests), 1)

    def test_signed_scope_purpose_time_and_framing_denials_precede_local_io(self):
        with service() as (port, requests):
            fixture = SampleFixture(port)
            app = self.install(fixture)
            foreign = replace(fixture.request, target=replace(fixture.request.target, receiver_id="f" * 32))
            for token in (
                fixture.token(private=ed25519.Ed25519PrivateKey.generate()),
                fixture.token(request=foreign),
                fixture.token(request=replace(fixture.request, check_digest="e" * 64)),
                fixture.token(request=replace(fixture.request, sample_ordinal=4)),
                fixture.token(purpose=core.DelegationKeyPurpose.GATEWAY_HTTP_VERIFICATION_SAMPLE_TRANSIT),
                fixture.token(expires_at=150), fixture.token(jti="different-outer-jti"),
            ):
                code, _, body = self.read(app, fixture, token)
                self.assertEqual(code, 401)
                self.assertNotIn(b"evidence", body)
                self.assertLess(len(body), 128)
            for options in (dict(query=b"check=other"), dict(chunks=(b"body",)),
                            dict(headers=[(b"authorization", b"Bearer " + fixture.token()),
                                          (b"content-length", b"1")]),
                            dict(raw_path=b"/__control/verification/%68ttp")):
                self.assertEqual(self.read(app, fixture, **options)[0], 400)
            self.assertEqual(requests, [])

    def test_explicit_and_file_backed_cross_wires_refuse_before_host_mutation(self):
        from control_plane_kit_server_sdk import stdlib as sdk_stdlib
        from tests.test_stdlib_control import ApplicationHandler
        with service() as (port, requests):
            fixture = SampleFixture(port)
            original = fixture.receiver.configuration
            other_target = replace(original.target, receiver_id="f" * 32)
            other_declaration = replace(original.declaration, surface=replace(original.declaration.surface,
                health_reads=(core.NodeHealthReadKind.LIVENESS,)))
            for other in (replace(original, target=other_target), replace(original, declaration=other_declaration)):
                binding = replace(fixture.binding, receiver_configuration=other,
                    configuration=replace(fixture.binding.configuration, target=other.target,
                                          declaration_identity=other.declaration.identity().value))
                self.assertEqual(binding.audience, fixture.binding.audience)
                for file_backed in (False, True):
                    with fixture.receiver.delivered():
                        configuration = None if file_backed else original
                        app = application.FastApiControlRouteTests()._app()
                        prior_routes, prior_lifespan = app.router.routes, app.router.lifespan_context
                        with self.assertRaises(ValueError):
                            sdk_fastapi.install_cpk_wrapper(app, configuration=configuration,
                                http_verification_binding=binding)
                        self.assertIs(app.router.routes, prior_routes)
                        self.assertIs(app.router.lifespan_context, prior_lifespan)
                        with self.assertRaises(ValueError):
                            sdk_stdlib.CpkThreadingHTTPServer(("127.0.0.1", 0), ApplicationHandler,
                                configuration=configuration, http_verification_binding=binding)
            self.assertEqual(requests, [])

    def test_threaded_stdlib_route_preserves_application_and_single_thread_refuses(self):
        from control_plane_kit_server_sdk import stdlib as sdk_stdlib
        from tests.test_stdlib_control import ApplicationHandler, StdlibControlTests
        with service() as (port, requests):
            fixture = SampleFixture(port)
            with self.assertRaises(ValueError):
                sdk_stdlib.CpkHTTPServer(("127.0.0.1", 0), ApplicationHandler,
                    configuration=fixture.receiver.configuration, http_verification_binding=fixture.binding)
            server = sdk_stdlib.CpkThreadingHTTPServer(("127.0.0.1", 0), ApplicationHandler,
                configuration=fixture.receiver.configuration, http_verification_binding=fixture.binding,
                clock=lambda: 150, http_sample_clock=lambda: 150)
            server.daemon_threads = False
            server.application_calls, server.application_logs = [], []
            thread = Thread(target=server.serve_forever, kwargs=dict(poll_interval=0.01))
            helper = StdlibControlTests()
            thread.start()
            try:
                raw = helper.request(server, target=b"/__control/verification/http", token=fixture.token())
                code, body = helper.response(raw)
                self.assertEqual(code, 200)
                result = HttpVerificationSampleResultCodec(fixture.request, fixture.check).decode(json.loads(body))
                self.assertEqual(result.outcome, VerificationOutcome.PASSED)
                self.assertEqual(len(requests), 1)
                raw = helper.request(server, target=b"/ordinary", token=b"unused")
                self.assertIn(b" 201 ", raw.split(b"\r\n", 1)[0])
                self.assertEqual(len(server.application_calls), 1)
                raw = helper.request(server, target=b"/__control/verification/http", token=b"bad")
                self.assertEqual(helper.response(raw)[0], 401)
                self.assertEqual(len(requests), 1)
            finally:
                server.shutdown()
                thread.join(3)
                server.server_close()
            self.assertFalse(thread.is_alive())
            self.assertEqual(server.socket.fileno(), -1)

    def test_unsafe_installed_path_refuses_before_local_io(self):
        with service() as (port, requests):
            fixture = SampleFixture(port, path="/ready\r\nx-injected: unsafe")
            app = application.FastApiControlRouteTests()._app()
            prior = app.router.routes
            with self.assertRaises(ValueError):
                sdk_fastapi.install_cpk_wrapper(app, configuration=fixture.receiver.configuration,
                    http_verification_binding=fixture.binding)
            self.assertIs(app.router.routes, prior)
            self.assertEqual(requests, [])


@contextmanager
def raw_service(response):
    import socket
    from threading import Event
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(2)
    stopped, closed = Event(), Event()
    def run():
        try:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(1)
                request = b""
                while b"\r\n\r\n" not in request:
                    part = connection.recv(4096)
                    if not part:
                        return
                    request += part
                if callable(response):
                    response(connection, stopped, closed)
                else:
                    connection.sendall(response)
        except (OSError, TimeoutError):
            closed.set()
    thread = Thread(target=run)
    thread.start()
    try:
        yield server.getsockname()[1], closed
    finally:
        stopped.set()
        server.close()
        thread.join(3)
        if thread.is_alive():
            raise AssertionError("test-owned HTTP service did not terminate")


class HttpSampleTransportTests(_SampleRouteHelpers, unittest.TestCase):
    def test_complete_framing_is_required_and_chunked_response_is_supported(self):
        for response, outcome, evidence in (
            (b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\nabc", VerificationOutcome.FAILED, None),
            (b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\nContent-Length: 3\r\n\r\nabc", VerificationOutcome.FAILED, None),
            (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Length: 3\r\n\r\nabc", VerificationOutcome.FAILED, None),
            (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n3\r\nabc\r\n0\r\n\r\n", VerificationOutcome.PASSED, 3),
            (b"HTTP/1.0 200 OK\r\n\r\nabc", VerificationOutcome.PASSED, 3),
            (b"not-http\r\n\r\n", VerificationOutcome.FAILED, None),
        ):
            with self.subTest(response=response[:12]), raw_service(response) as (port, _):
                fixture = SampleFixture(port)
                code, _, body = self.read(self.install(fixture), fixture)
                self.assertEqual(code, 200)
                result = HttpVerificationSampleResultCodec(fixture.request, fixture.check).decode(json.loads(body))
                self.assertEqual(result.outcome, outcome)
                self.assertEqual(None if result.evidence is None else result.evidence.response_bytes, evidence)

    def test_header_and_body_trickle_end_at_absolute_deadline_and_close_socket(self):
        import time
        import select
        for prefix in (b"HTTP/1.1 200 OK\r\nX-Trickle: ", b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n"):
            def trickle(connection, stopped, closed):
                connection.sendall(prefix)
                while not stopped.wait(0.025):
                    if select.select([connection], [], [], 0)[0] and connection.recv(1) == b"":
                        closed.set()
                        return
                    connection.sendall(b"x")
            with self.subTest(body=b"Content-Length" in prefix), raw_service(trickle) as (port, closed):
                fixture = SampleFixture(port, timeout=0.15)
                app = self.install(fixture)
                started = time.monotonic()
                code, _, body = self.read(app, fixture)
                elapsed = time.monotonic() - started
                result = HttpVerificationSampleResultCodec(fixture.request, fixture.check).decode(json.loads(body))
                self.assertEqual((code, result.outcome, result.evidence), (200, VerificationOutcome.TIMED_OUT, None))
                self.assertLess(elapsed, 0.8)
                self.assertTrue(closed.wait(0.5))

    def test_fractional_grant_remaining_time_is_not_rounded_up(self):
        import time
        def slow(connection, stopped, closed):
            connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\na")
            stopped.wait(1)
        with raw_service(slow) as (port, _):
            fixture = SampleFixture(port, timeout=1)
            app = application.FastApiControlRouteTests()._app()
            sdk_fastapi.install_cpk_wrapper(app, configuration=fixture.receiver.configuration,
                http_verification_binding=fixture.binding, clock=lambda: 150, http_sample_clock=lambda: 150.9)
            started = time.monotonic()
            code, _, body = self.read(app, fixture, fixture.token(expires_at=151))
            result = HttpVerificationSampleResultCodec(fixture.request, fixture.check).decode(json.loads(body))
            self.assertEqual((code, result.outcome, result.evidence), (200, VerificationOutcome.TIMED_OUT, None))
            self.assertLess(time.monotonic() - started, 0.6)
            helper = asgi.FastApiHealthRouteTests()
            health = fixture.receiver.health_request()
            health_code, _, health_body = asyncio.run(helper.asgi(app, token=fixture.receiver.token(health)))
            self.assertEqual(health_code, 200)
            self.assertEqual(core.ReceiverHealthReadResultCodec(health, fixture.receiver.declaration).decode(
                json.loads(health_body)).request, health)

    def test_companion_loader_and_present_invalid_opt_in_fail_closed(self):
        import os
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from control_plane_kit_core.http_verification_sample_installation import (
            HTTP_VERIFICATION_SAMPLES_CONFIGURATION_ENVIRONMENT as environment,
            HttpVerificationSampleReceiverConfigurationCodec,
        )
        from control_plane_kit_server_sdk.wrapper import load_http_verification_sample_configuration
        with service() as (port, requests), TemporaryDirectory() as temporary:
            fixture = SampleFixture(port)
            codec = HttpVerificationSampleReceiverConfigurationCodec()
            path = Path(temporary) / "samples.json"
            original = os.environ.get(environment)
            os.environ[environment] = str(path)
            try:
                path.write_bytes(codec.encode_canonical_bytes(fixture.binding.configuration))
                path.chmod(0o444)
                self.assertEqual(load_http_verification_sample_configuration(), fixture.binding.configuration)
                self.install(fixture)
                app = application.FastApiControlRouteTests()._app()
                prior = app.router.routes
                with self.assertRaises(ValueError):
                    sdk_fastapi.install_cpk_wrapper(app, configuration=fixture.receiver.configuration)
                self.assertIs(app.router.routes, prior)
                path.chmod(0o644)
                with self.assertRaises(ValueError):
                    load_http_verification_sample_configuration()
                path.write_bytes(b"invalid")
                path.chmod(0o444)
                with self.assertRaises(ValueError):
                    sdk_fastapi.install_cpk_wrapper(app, configuration=fixture.receiver.configuration,
                        http_verification_binding=fixture.binding)
                self.assertIs(app.router.routes, prior)
                self.assertEqual(requests, [])
            finally:
                if original is None:
                    del os.environ[environment]
                else:
                    os.environ[environment] = original

    def test_forbidden_version_and_status_framing_never_become_service_evidence(self):
        for response, expected in (
            (b"HTTP/1.0 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n", 200),
            (b"HTTP/1.1 204 No Content\r\nContent-Length: 0\r\n\r\n", 204),
        ):
            with self.subTest(status=expected), raw_service(response) as (port, _):
                fixture = SampleFixture(port)
                fixture.check = replace(fixture.check, expected_statuses=(expected,))
                fixture.binding = replace(fixture.bind(), provider_ports=(ProviderRuntimePort("control", port),))
                fixture.request = replace(fixture.request, check_digest=http_verification_check_digest(fixture.check))
                code, _, body = self.read(self.install(fixture), fixture)
                result = HttpVerificationSampleResultCodec(fixture.request, fixture.check).decode(json.loads(body))
                self.assertEqual((code, result.outcome, result.evidence), (200, VerificationOutcome.FAILED, None))

    def test_coalesced_framing_reads_consume_only_cap_plus_one_payload_bytes(self):
        from unittest.mock import patch
        from control_plane_kit_server_sdk.http_samples import HttpVerificationSampleReceiver
        for prefix, suffix in (
            (b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n", b""),
            (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n3e8\r\n", b"\r\n0\r\n\r\n"),
        ):
            class CoalescedSocket:
                def __init__(self):
                    self.position, self.payload_bytes, self.closed = 0, 0, False
                    self.data = prefix + b"x" * 1000 + suffix
                def settimeout(self, timeout):
                    return None
                def sendall(self, value):
                    return None
                def recv(self, maximum):
                    start, end = self.position, min(self.position + maximum, len(self.data))
                    self.position = end
                    self.payload_bytes += max(0, min(end, len(prefix) + 1000) - max(start, len(prefix)))
                    return self.data[start:end]
                def close(self):
                    self.closed = True
            fixture = SampleFixture(8080, cap=1)
            connection = CoalescedSocket()
            with patch("socket.create_connection", return_value=connection):
                body = HttpVerificationSampleReceiver(fixture.binding, lambda: 150).read(fixture.token())
            result = HttpVerificationSampleResultCodec(fixture.request, fixture.check).decode(json.loads(body))
            self.assertEqual(result.outcome, VerificationOutcome.MALFORMED)
            self.assertEqual(result.evidence.response_bytes, 1)
            self.assertEqual(connection.payload_bytes, 2)
            self.assertTrue(connection.closed)

    def test_every_installed_sample_key_is_actual_ed25519_before_publication(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from control_plane_kit_server_sdk import stdlib as sdk_stdlib
        from tests.test_stdlib_control import ApplicationHandler
        rsa_public = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")
        malformed = "-----BEGIN PUBLIC KEY-----\nYWJjZA==\n-----END PUBLIC KEY-----\n"
        with service() as (port, requests):
            fixture = SampleFixture(port)
            for pem in (rsa_public, malformed):
                bad_key = core.DelegationPublicKey("invalid-key", core.DelegationKeyAlgorithm.ED25519, pem)
                verifier = replace(fixture.binding.configuration.verifier, public_keys=(fixture.key, bad_key))
                binding = replace(fixture.binding, configuration=replace(fixture.binding.configuration, verifier=verifier))
                app = application.FastApiControlRouteTests()._app()
                prior, lifespan = app.router.routes, app.router.lifespan_context
                with self.assertRaises(ValueError):
                    sdk_fastapi.install_cpk_wrapper(app, configuration=fixture.receiver.configuration,
                        http_verification_binding=binding)
                self.assertIs(app.router.routes, prior)
                self.assertIs(app.router.lifespan_context, lifespan)
                with self.assertRaises(ValueError):
                    sdk_stdlib.CpkThreadingHTTPServer(("127.0.0.1", 0), ApplicationHandler,
                        configuration=fixture.receiver.configuration, http_verification_binding=binding)
            self.assertEqual(requests, [])
