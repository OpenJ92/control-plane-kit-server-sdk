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
from control_plane_kit_core.verification import HttpCheck, VerificationContract, VerificationPolicy
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


class HttpSampleRouteTests(unittest.TestCase):
    def install(self, fixture, **options):
        app = application.FastApiControlRouteTests()._app()
        try:
            sdk_fastapi.install_cpk_wrapper(app, configuration=fixture.receiver.configuration,
                clock=lambda: 150, http_verification_binding=fixture.binding, **options)
        except (TypeError, ValueError):
            self.fail("SDK wrapper refuses an independently installed HTTP sample binding")
        return app

    def read(self, app, fixture, token=None, **options):
        helper = asgi.FastApiHealthRouteTests()
        return asyncio.run(helper.asgi(app, path="/__control/verification/http",
            token=fixture.token() if token is None else token, **options))

    def test_signed_sample_uses_installed_local_check_and_correlated_result(self):
        with service() as (port, requests):
            fixture = SampleFixture(port)
            app = self.install(fixture)
            status, headers, body = self.read(app, fixture)
            self.assertEqual(status, 200)
            self.assertEqual(headers[b"cache-control"], b"no-store")
            result = HttpVerificationSampleResultCodec(fixture.request, fixture.check).decode(json.loads(body))
            self.assertEqual(result.outcome, core.VerificationOutcome.PASSED)
            self.assertEqual((result.evidence.status_code, result.evidence.response_bytes), (200, 5))
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0][0], "/ready")
            self.assertFalse(any(name.lower() == "authorization" for name, _ in requests[0][1]))
            self.assertNotIn(b"ready", body)
