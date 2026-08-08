from __future__ import annotations

import ast
import importlib
import importlib.util
import json
from pathlib import Path
from threading import Event, Lock, Thread
import unittest

from control_plane_kit_core import (
    ControlPlaneCommandCodec,
    ControlPlaneResultCodec,
    ControlPlaneStateCodec,
    ControlPlaneTransitionPrecondition,
    ControlPlaneVariableDescriptor,
    ControlPlaneVariableKind,
    ControlPlaneVariableOperationContract,
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
)
from control_plane_kit_core.node_control import MAX_NODE_CONTROL_PAYLOAD_BYTES


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "control_plane_kit_server_sdk"
REPLAY_MODULE = "control_plane_kit_server_sdk._replay"
RETENTION_NS = 300_000_000_000


class RequestSubclass(NodeControlCommandRequest):
    pass


class ResultCodecSubclass(NodeControlResultCodec):
    pass


class SensitiveCandidate:
    def __repr__(self) -> str:
        return "authorization: Bearer replay-secret"


class ExplodingReprCandidate:
    def __repr__(self) -> str:
        raise AssertionError("candidate repr must not be evaluated")


class ProcessControlSignal(BaseException):
    pass


class MutableClock:
    def __init__(self, now: object = 0) -> None:
        self._lock = Lock()
        self._now = now
        self.calls = 0

    def set(self, now: object) -> None:
        with self._lock:
            self._now = now

    def __call__(self) -> object:
        with self._lock:
            self.calls += 1
            now = self._now
        if isinstance(now, BaseException):
            raise now
        return now


def _reference(
    role: NodeControlGraphReferenceRole,
    value: str,
) -> NodeControlGraphReference:
    return NodeControlGraphReference(role, value)


def _target(*, node: str = "router") -> NodeControlTarget:
    return NodeControlTarget(
        workspace_id=_reference(
            NodeControlGraphReferenceRole.WORKSPACE,
            "workspace-1",
        ),
        graph_revision=_reference(
            NodeControlGraphReferenceRole.GRAPH_REVISION,
            "revision-7",
        ),
        node_id=_reference(NodeControlGraphReferenceRole.NODE, node),
        provider_socket_name=_reference(
            NodeControlGraphReferenceRole.PROVIDER_SOCKET,
            "control",
        ),
    )


def _descriptor(*, variable: str = "routing") -> ControlPlaneVariableDescriptor:
    return ControlPlaneVariableDescriptor(
        variable_name=_reference(
            NodeControlGraphReferenceRole.VARIABLE,
            variable,
        ),
        kind=ControlPlaneVariableKind.SCALAR,
        state_codec=ControlPlaneStateCodec.SCALAR_V1,
        operation_contracts=(
            ControlPlaneVariableOperationContract(
                operation=NodeControlOperation.READ_STATE,
                command_codec=None,
                result_codec=ControlPlaneResultCodec.STATE_V1,
            ),
            ControlPlaneVariableOperationContract(
                operation=NodeControlOperation.APPLY_COMMAND,
                command_codec=ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
                result_codec=ControlPlaneResultCodec.TRANSITION_V1,
            ),
        ),
    )


def _request(
    *,
    request_id: str = "request-1",
    key: str = "idempotency-1",
    node: str = "router",
    variable: str = "routing",
    value: str = "target-b",
) -> NodeControlCommandRequest:
    codec = ControlPlaneCommandCodec.REPLACE_SCALAR_V1
    return NodeControlCommandRequest(
        target=_target(node=node),
        variable_name=_reference(NodeControlGraphReferenceRole.VARIABLE, variable),
        operation=NodeControlOperation.APPLY_COMMAND,
        request_id=request_id,
        idempotency_key=key,
        command_codec=codec,
        precondition=ControlPlaneTransitionPrecondition(0),
        payload=NodeControlPayload(
            codec=codec,
            state=ScalarControlState(value),
        ),
    )


def _read_request(*, key: str = "idempotency-1") -> NodeControlCommandRequest:
    return NodeControlCommandRequest(
        target=_target(),
        variable_name=_reference(
            NodeControlGraphReferenceRole.VARIABLE,
            "routing",
        ),
        operation=NodeControlOperation.READ_STATE,
        request_id="read-1",
        idempotency_key=key,
    )


def _success(request: NodeControlCommandRequest) -> NodeControlTransitionSucceeded:
    return NodeControlTransitionSucceeded(
        request_id=request.request_id,
        version=1,
        evidence=NodeControlEvidence(NodeControlEvidenceCode.APPLIED),
    )


class ProcessLocalReplayTests(unittest.TestCase):
    def _module(self):
        specification = importlib.util.find_spec(REPLAY_MODULE)
        self.assertIsNotNone(
            specification,
            "missing process-local replay module",
        )
        return importlib.import_module(REPLAY_MODULE)

    def _coordinator(self, **kwargs):
        return self._module()._ProcessLocalNodeControlReplay(**kwargs)

    def _codec(self) -> NodeControlResultCodec:
        return NodeControlResultCodec(_descriptor())

    def _execute(self, coordinator, request, dispatch, *, codec=None):
        return coordinator.execute(
            request,
            result_codec=self._codec() if codec is None else codec,
            dispatch=dispatch,
        )

    def _join(self, thread: Thread) -> None:
        thread.join(3)
        self.assertFalse(thread.is_alive(), "replay thread did not terminate")

    def test_exact_apply_results_are_copied_and_same_digest_dispatches_once(self) -> None:
        coordinator = self._coordinator()
        for index, result_factory in enumerate((
            _success,
            lambda request: NodeControlRejected(
                request_id=request.request_id,
                operation=NodeControlOperation.APPLY_COMMAND,
                evidence=NodeControlEvidence(
                    NodeControlEvidenceCode.PRECONDITION_FAILED
                ),
            ),
            lambda request: NodeControlFailed(
                request_id=request.request_id,
                operation=NodeControlOperation.APPLY_COMMAND,
            ),
        )):
            with self.subTest(result_factory=result_factory):
                request = _request(
                    request_id=f"request-{index}",
                    key=f"key-{index}",
                )
                calls = 0
                produced = result_factory(request)

                def dispatch():
                    nonlocal calls
                    calls += 1
                    return produced

                first = self._execute(coordinator, request, dispatch)
                replayed = self._execute(coordinator, request, dispatch)

                self.assertEqual(first, produced)
                self.assertEqual(replayed, produced)
                self.assertIsNot(first, produced)
                self.assertIsNot(replayed, first)
                self.assertEqual(calls, 1)
                self.assertEqual(self._codec().decode(self._codec().encode(first)), first)

    def test_compact_utf8_terminal_profile_and_exact_byte_bound(self) -> None:
        module = self._module()
        serialize = module._serialize_terminal_descriptor
        descriptor = {"z": "caf\u00e9", "a": 1}

        encoded = serialize(descriptor)

        self.assertEqual(encoded, b'{"a":1,"z":"caf\xc3\xa9"}')
        self.assertEqual(json.loads(encoded.decode("utf-8")), descriptor)
        boundary = {"x": "a" * (MAX_NODE_CONTROL_PAYLOAD_BYTES - 8)}
        self.assertEqual(len(serialize(boundary)), MAX_NODE_CONTROL_PAYLOAD_BYTES)
        with self.assertRaises(Exception) as raised:
            serialize({"x": "a" * (MAX_NODE_CONTROL_PAYLOAD_BYTES - 7)})
        self.assertLessEqual(len(str(raised.exception)), 96)
        self.assertNotIn("aaaa", str(raised.exception))
        with self.assertRaises(Exception):
            serialize({"x": float("nan")})

    def test_oversize_owner_result_publishes_only_bounded_closed_failure(self) -> None:
        coordinator = self._coordinator()
        request = _request()
        codec = self._codec()
        original_encode = codec.encode

        def oversize_encode(result):
            if isinstance(result, NodeControlFailed):
                return original_encode(result)
            return {"x": "a" * MAX_NODE_CONTROL_PAYLOAD_BYTES}

        codec.encode = oversize_encode
        calls = 0

        def dispatch():
            nonlocal calls
            calls += 1
            return _success(request)

        first = self._execute(coordinator, request, dispatch, codec=codec)
        replayed = self._execute(coordinator, request, dispatch, codec=codec)

        self.assertIsInstance(first, NodeControlFailed)
        self.assertEqual(replayed, first)
        self.assertEqual(calls, 1)
        self.assertNotIn("aaaa", repr(coordinator))
        self.assertNotIn(request.idempotency_key, repr(coordinator))

    def test_exact_private_error_categories_are_fixed_and_redacted(self) -> None:
        module = self._module()
        expected = {
            module._NodeControlReplayContractError:
                "node-control replay call is invalid",
            module._NodeControlReplayConflict:
                "node-control replay intent conflicts",
            module._NodeControlReplayCapacityExhausted:
                "node-control replay capacity is exhausted",
            module._NodeControlReplayReentry:
                "node-control replay owner cannot re-enter",
        }
        for error_type, message in expected.items():
            with self.subTest(error_type=error_type.__name__):
                error = error_type()
                self.assertEqual(str(error), message)
                self.assertLessEqual(len(repr(error)), 128)
                self.assertNotIn("secret", repr(error))
                self.assertTrue(issubclass(error_type, module._NodeControlReplayError))

    def test_invalid_call_shape_and_initial_clock_create_no_reservation(self) -> None:
        module = self._module()
        request = _request()
        calls = 0

        def dispatch():
            nonlocal calls
            calls += 1
            return _success(request)

        for capacity in (True, 0, 4097):
            with self.subTest(capacity=capacity):
                with self.assertRaises(module._NodeControlReplayContractError):
                    self._coordinator(capacity=capacity)

        coordinator = self._coordinator()
        request_subclass = RequestSubclass(
            target=request.target,
            variable_name=request.variable_name,
            operation=request.operation,
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            command_codec=request.command_codec,
            precondition=request.precondition,
            payload=request.payload,
        )
        invalid_calls = (
            (_read_request(), self._codec(), dispatch),
            (SensitiveCandidate(), self._codec(), dispatch),
            (ExplodingReprCandidate(), self._codec(), dispatch),
            (request_subclass, self._codec(), dispatch),
            (request, ResultCodecSubclass(_descriptor()), dispatch),
            (request, self._codec(), SensitiveCandidate()),
        )
        for candidate, codec, candidate_dispatch in invalid_calls:
            with self.subTest(candidate=type(candidate).__name__):
                with self.assertRaises(module._NodeControlReplayContractError) as raised:
                    coordinator.execute(
                        candidate,
                        result_codec=codec,
                        dispatch=candidate_dispatch,
                    )
                self.assertIsNone(raised.exception.__cause__)
                self.assertIsNone(raised.exception.__context__)
                self.assertEqual(
                    str(raised.exception),
                    "node-control replay call is invalid",
                )
        self.assertEqual(calls, 0)

        clock = MutableClock(RuntimeError("authorization: Bearer clock-secret"))
        coordinator = self._coordinator(clock_ns=clock)
        with self.assertRaises(module._NodeControlReplayContractError) as raised:
            self._execute(coordinator, request, dispatch)
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        self.assertNotIn("secret", repr(raised.exception))
        clock.set(0)
        self.assertEqual(self._execute(coordinator, request, dispatch), _success(request))
        self.assertEqual(calls, 1)

    def test_changed_intent_conflicts_globally_without_second_dispatch(self) -> None:
        module = self._module()
        coordinator = self._coordinator()
        original = _request()
        calls = 0

        def dispatch():
            nonlocal calls
            calls += 1
            return _success(original)

        self._execute(coordinator, original, dispatch)
        changed_requests = (
            _request(key=original.idempotency_key, request_id="request-2"),
            _request(key=original.idempotency_key, node="router-2"),
            _request(key=original.idempotency_key, variable="other"),
            _request(key=original.idempotency_key, value="target-c"),
        )
        for changed in changed_requests:
            with self.subTest(request_id=changed.request_id, node=changed.target.node_id):
                with self.assertRaises(module._NodeControlReplayConflict) as raised:
                    self._execute(coordinator, changed, dispatch)
                self.assertIsNone(raised.exception.__cause__)
                self.assertIsNone(raised.exception.__context__)
        self.assertEqual(calls, 1)

    def test_inflight_is_nonprunable_capacity_counted_and_waiters_converge(self) -> None:
        module = self._module()
        clock = MutableClock(0)
        coordinator = self._coordinator(capacity=1, clock_ns=clock)
        request = _request()
        entered = Event()
        release = Event()
        owner_results: list[object] = []
        waiter_results: list[object] = []

        def dispatch():
            entered.set()
            self.assertTrue(release.wait(3), "owner release timed out")
            return _success(request)

        owner = Thread(
            target=lambda: owner_results.append(
                self._execute(coordinator, request, dispatch)
            )
        )
        owner.start()
        self.assertTrue(entered.wait(3), "owner did not enter dispatch")
        waiter = Thread(
            target=lambda: waiter_results.append(
                self._execute(coordinator, request, dispatch)
            )
        )
        waiter.start()
        clock.set(RETENTION_NS * 2)
        with self.assertRaises(module._NodeControlReplayCapacityExhausted):
            self._execute(
                coordinator,
                _request(request_id="other", key="other-key"),
                lambda: self.fail("capacity dispatch must not run"),
            )
        with self.assertRaises(module._NodeControlReplayConflict):
            self._execute(
                coordinator,
                _request(key=request.idempotency_key, value="target-c"),
                lambda: self.fail("conflict dispatch must not run"),
            )
        release.set()
        self._join(owner)
        self._join(waiter)
        self.assertEqual(owner_results, [_success(request)])
        self.assertEqual(waiter_results, [_success(request)])

    def test_unrelated_key_progresses_while_an_owner_is_blocked(self) -> None:
        coordinator = self._coordinator(capacity=2)
        first = _request()
        second = _request(request_id="request-2", key="idempotency-2")
        entered = Event()
        release = Event()
        owner_results: list[object] = []

        def blocked_dispatch():
            entered.set()
            self.assertTrue(release.wait(3), "owner release timed out")
            return _success(first)

        owner = Thread(
            target=lambda: owner_results.append(
                self._execute(coordinator, first, blocked_dispatch)
            )
        )
        owner.start()
        self.assertTrue(entered.wait(3), "owner did not enter dispatch")
        second_result = self._execute(coordinator, second, lambda: _success(second))
        release.set()
        self._join(owner)

        self.assertEqual(second_result, _success(second))
        self.assertEqual(owner_results, [_success(first)])

    def test_terminal_expiry_starts_at_publication_and_never_evicts_early(self) -> None:
        module = self._module()
        clock = MutableClock(5)
        coordinator = self._coordinator(capacity=1, clock_ns=clock)
        first = _request()
        second = _request(request_id="request-2", key="idempotency-2")

        self._execute(coordinator, first, lambda: _success(first))
        clock.set(5 + RETENTION_NS - 1)
        with self.assertRaises(module._NodeControlReplayCapacityExhausted):
            self._execute(coordinator, second, lambda: _success(second))
        clock.set(5 + RETENTION_NS)
        self.assertEqual(
            self._execute(coordinator, second, lambda: _success(second)),
            _success(second),
        )

    def test_owner_failures_publish_one_closed_failure_without_diagnostics(self) -> None:
        coordinator = self._coordinator()
        request = _request()
        cases = (
            lambda: (_ for _ in ()).throw(
                RuntimeError("authorization: Bearer dispatch-secret")
            ),
            lambda: SensitiveCandidate(),
            lambda: ExplodingReprCandidate(),
            lambda: NodeControlReadStateSucceeded(
                request_id=request.request_id,
                state_codec=ControlPlaneStateCodec.SCALAR_V1,
                version=0,
                state=ScalarControlState("target-a"),
            ),
            lambda: NodeControlTransitionSucceeded(
                request_id="wrong-request",
                version=1,
                evidence=NodeControlEvidence(NodeControlEvidenceCode.APPLIED),
            ),
        )
        for index, dispatch in enumerate(cases):
            with self.subTest(index=index):
                candidate = _request(
                    request_id=f"failure-{index}",
                    key=f"failure-key-{index}",
                )
                calls = 0

                def counted_dispatch():
                    nonlocal calls
                    calls += 1
                    return dispatch()

                result = self._execute(coordinator, candidate, counted_dispatch)
                replayed = self._execute(coordinator, candidate, counted_dispatch)
                self.assertIsInstance(result, NodeControlFailed)
                self.assertEqual(result.request_id, candidate.request_id)
                self.assertEqual(replayed, result)
                self.assertEqual(calls, 1)
                for rendered in (repr(result), repr(replayed), repr(coordinator)):
                    self.assertNotIn("secret", rendered)
                    self.assertNotIn(candidate.idempotency_key, rendered)

    def test_process_control_publishes_before_reraising_and_wakes_replay(self) -> None:
        coordinator = self._coordinator(capacity=1)
        request = _request()

        with self.assertRaises(ProcessControlSignal):
            self._execute(
                coordinator,
                request,
                lambda: (_ for _ in ()).throw(ProcessControlSignal()),
            )
        replayed = self._execute(
            coordinator,
            request,
            lambda: self.fail("process-control replay must not redispatch"),
        )
        self.assertIsInstance(replayed, NodeControlFailed)

    def test_same_owner_reentry_fails_without_deadlock(self) -> None:
        module = self._module()
        coordinator = self._coordinator()
        request = _request()
        nested_errors: list[BaseException] = []

        def dispatch():
            try:
                self._execute(
                    coordinator,
                    request,
                    lambda: self.fail("nested dispatch must not run"),
                )
            except BaseException as error:
                nested_errors.append(error)
            return _success(request)

        result = self._execute(coordinator, request, dispatch)

        self.assertEqual(result, _success(request))
        self.assertEqual(len(nested_errors), 1)
        self.assertIsInstance(nested_errors[0], module._NodeControlReplayReentry)

    def test_invalid_completion_clock_publishes_unprunable_closed_failure(self) -> None:
        module = self._module()
        clock = MutableClock(10)
        coordinator = self._coordinator(capacity=1, clock_ns=clock)
        request = _request()

        def dispatch():
            clock.set(9)
            return _success(request)

        result = self._execute(coordinator, request, dispatch)
        self.assertIsInstance(result, NodeControlFailed)
        clock.set(2**63 - 1)
        replayed = self._execute(
            coordinator,
            request,
            lambda: self.fail("unprunable result must not redispatch"),
        )
        self.assertEqual(replayed, result)
        with self.assertRaises(module._NodeControlReplayCapacityExhausted):
            self._execute(
                coordinator,
                _request(request_id="other", key="other-key"),
                lambda: self.fail("unprunable capacity must stay occupied"),
            )

    def test_completion_clock_exceptions_publish_before_return_or_reraise(self) -> None:
        for index, completion_error in enumerate(
            (
                RuntimeError("authorization: Bearer clock-secret"),
                ProcessControlSignal(),
            )
        ):
            with self.subTest(error_type=type(completion_error).__name__):
                clock = MutableClock(10)
                coordinator = self._coordinator(capacity=1, clock_ns=clock)
                request = _request(
                    request_id=f"clock-{index}",
                    key=f"clock-key-{index}",
                )

                def dispatch():
                    clock.set(completion_error)
                    return _success(request)

                if isinstance(completion_error, Exception):
                    result = self._execute(coordinator, request, dispatch)
                else:
                    with self.assertRaises(ProcessControlSignal):
                        self._execute(coordinator, request, dispatch)
                    result = NodeControlFailed(
                        request_id=request.request_id,
                        operation=NodeControlOperation.APPLY_COMMAND,
                    )
                clock.set(2**63 - 1)
                replayed = self._execute(
                    coordinator,
                    request,
                    lambda: self.fail("clock failure must not redispatch"),
                )
                self.assertEqual(replayed, result)
                self.assertNotIn("secret", repr(replayed))

    def test_coordinator_instances_are_isolated(self) -> None:
        request = _request()
        first = self._coordinator()
        second = self._coordinator()
        calls = 0

        def dispatch():
            nonlocal calls
            calls += 1
            return _success(request)

        self._execute(first, request, dispatch)
        self._execute(second, request, dispatch)
        self.assertEqual(calls, 2)

    def test_private_module_has_no_outer_runtime_or_root_export(self) -> None:
        module = self._module()
        path = Path(module.__file__).resolve()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        forbidden = {
            "asyncio",
            "control_plane_kit_operations",
            "cryptography",
            "fastapi",
            "jwt",
            "psycopg",
        }
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
        self.assertEqual(imports & forbidden, set())

        root = importlib.import_module("control_plane_kit_server_sdk")
        self.assertNotIn("_ProcessLocalNodeControlReplay", root.__all__)
        self.assertFalse(hasattr(root, "_ProcessLocalNodeControlReplay"))
        self.assertFalse(hasattr(module._ProcessLocalNodeControlReplay(), "__dict__"))

    def test_docs_fix_process_local_replay_and_synchronous_route_handoff(self) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        decision_path = (
            REPOSITORY_ROOT
            / "docs"
            / "decisions"
            / "0011-process-local-node-control-replay.md"
        )
        self.assertTrue(decision_path.is_file(), "missing replay decision 0011")
        decision = decision_path.read_text(encoding="utf-8")

        for document in (readme, decision):
            for required in (
                "process-local",
                "not durable",
                "16,384",
                "300 seconds",
                "#1506",
                "#1507",
            ):
                with self.subTest(document=document[:24], required=required):
                    self.assertIn(required, document)
        for required in (
            "synchronous",
            "worker thread",
            "one coordinator",
            "admission before replay",
        ):
            with self.subTest(required=required):
                self.assertIn(required, decision)
        for excluded in (
            "provides durable replay",
            "authenticates the request",
            "proves graph membership",
        ):
            with self.subTest(excluded=excluded):
                self.assertNotIn(excluded, decision)


if __name__ == "__main__":
    unittest.main()
