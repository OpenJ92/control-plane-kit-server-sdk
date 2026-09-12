"""Closed workload callback interpretation through the accepted real verifier."""
from dataclasses import replace
import unittest

import control_plane_kit_core as core
import control_plane_kit_server_sdk as sdk
from control_plane_kit_server_sdk.health import (
    WorkloadNodeHealthReadDispatcher, WorkloadNodeHealthReadDispatchError,
)
from control_plane_kit_server_sdk.verification import WorkloadNodeHealthReadVerificationError
from tests import test_health_verification as credentials


class HealthDispatchTests(unittest.TestCase):
    def setUp(self):
        self.fixture = credentials.SignedHealthReadVerificationTests()
        self.fixture.setUp()
        self.calls = []
        self.outcome = core.NodeHealthReadOutcome.HEALTHY

    def live(self):
        self.calls.append(core.NodeHealthReadKind.LIVENESS)
        return self.outcome

    def ready(self):
        self.calls.append(core.NodeHealthReadKind.READINESS)
        return self.outcome

    def dispatcher(self, **changes):
        return WorkloadNodeHealthReadDispatcher(**{
            "target": self.fixture.target, "runtime_id": self.fixture.runtime,
            "declaration": self.fixture.declaration, "verifier": self.fixture.verifier(),
            "liveness": self.live, "readiness": self.ready, **changes,
        })

    def test_exact_callback_coverage_and_sync_zero_argument_shape_before_invocation(self):
        async def async_callback():
            return self.outcome
        def needs_argument(value):
            return value
        for change in (
            {"readiness": None}, {"liveness": object()}, {"readiness": async_callback},
            {"readiness": needs_argument}, {"runtime_id": self.fixture.target.node_id},
            {"target": replace(self.fixture.target, provider_socket_name=replace(
                self.fixture.target.provider_socket_name, value="other",
            ))}, {"verifier": object()},
        ):
            with self.subTest(field=tuple(change)), self.assertRaises(ValueError) as caught:
                self.dispatcher(**change)
            self.assertIsNone(caught.exception.__cause__)
            self.assertIsNone(caught.exception.__context__)
        live_only = replace(self.fixture.declaration, surface=replace(
            self.fixture.declaration.surface, health_reads=(core.NodeHealthReadKind.LIVENESS,),
        ))
        with self.assertRaises(ValueError):
            self.dispatcher(declaration=live_only)
        admitted = self.dispatcher(declaration=live_only, readiness=None)
        self.assertEqual(admitted.declaration, live_only)
        self.assertEqual(self.calls, [])
        self.assertEqual(repr(admitted), "WorkloadNodeHealthReadDispatcher()")
        with self.assertRaises(AttributeError):
            admitted.target = self.fixture.target
        self.assertNotIn("WorkloadNodeHealthReadDispatcher", sdk.__all__)

    def test_admission_denial_precedes_callbacks_and_same_request_has_no_cache(self):
        dispatcher = self.dispatcher()
        request = self.fixture.request
        foreign = replace(request, runtime_id=replace(request.runtime_id, value="other-runtime"))
        for token in (
            self.fixture.token(private=self.fixture.other_private),
            self.fixture.token(self.fixture.grant(foreign)),
            self.fixture.token(self.fixture.grant(expires_at=150)),
        ):
            with self.assertRaises(WorkloadNodeHealthReadVerificationError):
                dispatcher.read(token, route_kind=request.kind, candidate=None)
        with self.assertRaises(WorkloadNodeHealthReadVerificationError):
            dispatcher.read(self.fixture.token(), route_kind=request.kind, candidate=b"")
        self.assertEqual(self.calls, [])
        for outcome in core.NodeHealthReadOutcome:
            self.outcome = outcome
            result = dispatcher.read(self.fixture.token(), route_kind=request.kind, candidate=None)
            self.assertIs(type(result), core.NodeHealthReadResult)
            self.assertEqual(result.request, request)
            self.assertEqual(result.outcome, outcome)
            self.assertEqual(result.declaration, self.fixture.declaration)
        self.assertEqual(self.calls, [request.kind] * 4)

    def test_bad_callback_returns_and_exceptions_are_nonsemantic_redacted_failures(self):
        def fail():
            raise RuntimeError("authorization: Bearer callback-private-marker")
        async def accidental_coroutine():
            return core.NodeHealthReadOutcome.HEALTHY
        for callback in (fail, lambda: "healthy", lambda: None, lambda: {}, lambda: accidental_coroutine()):
            dispatcher = self.dispatcher(readiness=callback)
            with self.assertRaises(WorkloadNodeHealthReadDispatchError) as caught:
                dispatcher.read(self.fixture.token(), route_kind=self.fixture.request.kind, candidate=None)
            self.assertEqual(str(caught.exception), "workload health read failed")
            self.assertEqual(vars(caught.exception), {})
            self.assertIsNone(caught.exception.__cause__)
            self.assertIsNone(caught.exception.__context__)
        def interrupted():
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.dispatcher(readiness=interrupted).read(
                self.fixture.token(), route_kind=self.fixture.request.kind, candidate=None,
            )


if __name__ == "__main__":
    unittest.main()
