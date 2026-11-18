"""Live receiver families and existing local result/replay laws (L4–L11)."""
import asyncio
from dataclasses import replace
import json
import unittest

from cryptography.hazmat.primitives.asymmetric import ed25519

import control_plane_kit_core as core
from control_plane_kit_server_sdk import ControlPlaneInvocationContext
from control_plane_kit_server_sdk import fastapi as sdk_fastapi
from control_plane_kit_server_sdk.wrapper import WrapperSetupError
from control_plane_kit_server_sdk._replay import (
    _ProcessLocalNodeControlReplay, _NodeControlReplayContractError, _NodeControlReplayConflict,
)
from tests.receiver_fixtures import ReceiverFixture
from tests import test_fastapi_control_routes as application
from tests import test_fastapi_health_routes as asgi


class ReceiverVerificationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ReceiverFixture(mixed=True)
        self.assertEqual(core.ReceiverNodeControlConfigurationCodec().decode_bytes(self.fixture.encoded),
                         self.fixture.configuration)

    def app(self, **options):
        app = application.FastApiControlRouteTests()._app()
        try:
            sdk_fastapi.install_cpk_wrapper(app, configuration=self.fixture.configuration,
                                           clock=lambda: 150, **options)
        except WrapperSetupError:
            self.fail("SDK setup refuses valid receiver material before receiving protected requests")
        return app

    async def call(self, app, request, *, token=None):
        helper = asgi.FastApiHealthRouteTests()
        options = {}
        if type(request) is core.ReceiverControlSurfaceReadRequest:
            options["path"] = "/__control/" + request.kind.value
        elif type(request) is core.ReceiverNodeControlRequest:
            options["path"] = "/__control/variables/" + request.variable_name.value
            if request.operation is core.NodeControlOperation.APPLY_COMMAND:
                options.update(method="POST", path=options["path"] + "/commands",
                               chunks=(request.canonical_bytes(),))
        return await helper.asgi(app, token=self.fixture.token(request) if token is None else token, **options)

    def test_receiver_health_profiles_trust_and_claims_refuse_before_callbacks(self):
        calls = []
        def readiness():
            calls.append(1)
            return core.NodeHealthReadOutcome.HEALTHY
        async def exercise():
            app = self.app(readiness=readiness)
            request = self.fixture.health_request()
            async with app.router.lifespan_context(app):
                self.assertEqual((await self.call(app, request))[0], 200)
                calls.clear()
                tokens = (
                    self.fixture.token(request, private=ed25519.Ed25519PrivateKey.generate()),
                    self.fixture.token(request, grant_changes={"expires_at": 150}),
                    self.fixture.token(request, document_changes={"profile": "workload-node-health-read-grant.v1"}),
                    self.fixture.token(request, document_changes={"profile": "workload-node-health-read-grant.v9"}),
                    self.fixture.token(request, document_changes={"runtime_id": "runtime-a"}),
                    self.fixture.token(request, document_changes={"unexpected": "claim"}),
                    self.fixture.token(self.fixture.surface_request(core.NodeControlSurfaceReadKind.STATUS)),
                )
                for token in tokens:
                    code, _, body = await self.call(app, request, token=token)
                    self.assertEqual(code, 401)
                    self.assertNotIn(b"outcome", body)
                self.assertEqual(calls, [])
        asyncio.run(exercise())

    def test_local_commands_and_surface_keep_declared_semantics_and_origin_digest(self):
        async def exercise():
            variable = application.RecordingVariable("routing")
            app = self.app(variables=(variable,))
            for kind in core.NodeControlSurfaceReadKind:
                request = self.fixture.surface_request(kind)
                code, _, body = await self.call(app, request)
                self.assertEqual(code, 200)
                result = core.ReceiverControlSurfaceReadResultCodec(request, self.fixture.declaration).decode(json.loads(body))
                self.assertEqual(result.profile, core.ReceiverControlSurfaceReadResultProfile.V3)
            for operation in core.NodeControlOperation:
                request = self.fixture.command_request(operation)
                self.assertEqual(core.ReceiverNodeControlRequestCodec().decode(request.descriptor()), request)
                for _ in range(2):
                    code, _, body = await self.call(app, request)
                    self.assertEqual(code, 200)
                    result = core.ReceiverNodeControlResultCodec(request, self.fixture.declaration).decode(json.loads(body))
                    self.assertEqual(result.request_digest, request.canonical_digest())
                    self.assertEqual(body, result.canonical_bytes())
            self.assertEqual(variable.apply_calls, 1)
            self.assertEqual(variable.read_calls, 2)
        asyncio.run(exercise())

    def test_invocation_context_accepts_the_exact_receiver_request(self):
        for operation in core.NodeControlOperation:
            request = self.fixture.command_request(operation)
            self.assertEqual(core.ReceiverNodeControlRequestCodec().decode(request.descriptor()), request)
            try:
                context = ControlPlaneInvocationContext(request)
            except TypeError:
                self.fail("SDK invocation context refuses the accepted receiver request type")
            self.assertIs(context.request, request)
            self.assertNotIn(request.target.receiver_id, repr(context))

    def test_receiver_replay_retains_correlated_terminal_without_redispatch(self):
        request = self.fixture.command_request(core.NodeControlOperation.APPLY_COMMAND)
        codec = core.ReceiverNodeControlResultCodec(request, self.fixture.declaration)
        result = codec.result(core.NodeControlTransitionSucceeded(
            request.request_id, 1, core.NodeControlEvidence(core.NodeControlEvidenceCode.APPLIED)))
        self.assertEqual(codec.decode(codec.encode(result)), result)
        replay = _ProcessLocalNodeControlReplay()
        calls = []
        def dispatch():
            calls.append(1)
            return result
        try:
            first = replay.execute(request, result_codec=codec, dispatch=dispatch)
        except _NodeControlReplayContractError:
            self.fail("SDK replay refuses the accepted receiver request and correlated result codec")
        second = replay.execute(request, result_codec=codec, dispatch=dispatch)
        self.assertEqual(first, result)
        self.assertEqual(second, result)
        self.assertIsNot(first, second)
        self.assertEqual(calls, [1])
        changed = replace(request, authority_context=core.NodeControlAuthorityContext("graph-b", "projection-b"))
        changed_codec = core.ReceiverNodeControlResultCodec(changed, self.fixture.declaration)
        with self.assertRaises(_NodeControlReplayConflict):
            replay.execute(changed, result_codec=changed_codec, dispatch=dispatch)
        self.assertEqual(calls, [1])

    def test_variable_only_wrapper_preserves_surface_and_local_commands(self):
        self.fixture = ReceiverFixture(mixed=True, health=False)
        variable = application.RecordingVariable("routing")
        app = self.app(variables=(variable,))
        async def exercise():
            for kind in core.NodeControlSurfaceReadKind:
                self.assertEqual((await self.call(app, self.fixture.surface_request(kind)))[0], 200)
            for operation in core.NodeControlOperation:
                request = self.fixture.command_request(operation)
                code, _, body = await self.call(app, request)
                self.assertEqual(code, 200)
                result = core.ReceiverNodeControlResultCodec(request, self.fixture.declaration).decode(json.loads(body))
                self.assertEqual(result.request_digest, request.canonical_digest())
            self.assertEqual((variable.read_calls, variable.apply_calls), (1, 1))
        asyncio.run(exercise())

    def test_retry_authenticates_before_replay_and_changed_context_conflicts(self):
        variable = application.RecordingVariable("routing")
        app = self.app(variables=(variable,))
        request = self.fixture.command_request(core.NodeControlOperation.APPLY_COMMAND)
        async def exercise():
            first = await self.call(app, request)
            self.assertEqual(first[0], 200)
            for token in (
                self.fixture.token(request, private=ed25519.Ed25519PrivateKey.generate()),
                self.fixture.token(request, grant_changes={"expires_at": 150}),
                self.fixture.token(request, document_changes={"profile": "workload-node-control-grant.v1"}),
            ):
                self.assertEqual((await self.call(app, request, token=token))[0], 401)
            self.assertEqual(await self.call(app, request), first)
            changed = replace(request, authority_context=core.NodeControlAuthorityContext("graph-b", "projection-b"))
            self.assertEqual((await self.call(app, changed))[0], 409)
            self.assertEqual(variable.apply_calls, 1)
        asyncio.run(exercise())

    def test_replay_uses_canonical_correlation_when_python_equality_agrees(self):
        request = self.fixture.command_request(core.NodeControlOperation.APPLY_COMMAND,
            payload=core.NodeControlPayload(core.ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
                                            core.ScalarControlState(True)))
        numeric = replace(request, payload=core.NodeControlPayload(
            core.ControlPlaneCommandCodec.REPLACE_SCALAR_V1, core.ScalarControlState(1)))
        self.assertEqual(request, numeric)
        self.assertNotEqual(request.canonical_digest(), numeric.canonical_digest())
        codec = core.ReceiverNodeControlResultCodec(request, self.fixture.declaration)
        other_codec = core.ReceiverNodeControlResultCodec(numeric, self.fixture.declaration)
        wrong = other_codec.result(core.NodeControlTransitionSucceeded(
            numeric.request_id, 1, core.NodeControlEvidence(core.NodeControlEvidenceCode.APPLIED)))
        replay = _ProcessLocalNodeControlReplay()
        calls = []
        def dispatch():
            calls.append(1)
            return wrong
        with self.assertRaises(_NodeControlReplayContractError):
            replay.execute(request, result_codec=other_codec, dispatch=dispatch)
        self.assertEqual(calls, [])
        self.assertEqual(replay._entries, {})
        first = replay.execute(request, result_codec=codec, dispatch=dispatch)
        second = replay.execute(request, result_codec=codec, dispatch=dispatch)
        self.assertIs(type(first.outcome), core.NodeControlFailed)
        self.assertEqual(first.request_digest, request.canonical_digest())
        self.assertEqual(first, second)
        self.assertEqual(calls, [1])
        self.assertLessEqual(len(codec.encode_canonical_bytes(first)), 16_384)

    def test_foreign_receiver_does_not_mask_command_binding_denial(self):
        variable = application.RecordingVariable("routing")
        app = self.app(variables=(variable,))
        request = self.fixture.command_request(core.NodeControlOperation.APPLY_COMMAND,
            target=replace(self.fixture.target, receiver_id="b" * 32))
        async def exercise():
            self.assertEqual((await self.call(app, request))[0], 403)
            for changes in (
                {"request_id": "other-request"},
                {"idempotency_key": "other-key"},
                {"command_codec": core.ControlPlaneCommandCodec.REPLACE_MAP_V1},
                {"variable_name": replace(request.variable_name, value="other-variable")},
                {"operation": core.NodeControlOperation.READ_STATE, "command_codec": None},
            ):
                with self.subTest(fields=tuple(changes)):
                    token = self.fixture.token(request, grant_changes=changes)
                    self.assertEqual((await self.call(app, request, token=token))[0], 401)
            self.assertEqual(variable.apply_calls, 0)
            local = replace(request, target=self.fixture.target)
            self.assertEqual((await self.call(app, local))[0], 200)
            self.assertEqual(variable.apply_calls, 1)
        asyncio.run(exercise())
