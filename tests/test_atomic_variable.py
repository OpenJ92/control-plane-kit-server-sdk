from __future__ import annotations

import ast
import importlib
import importlib.util
from pathlib import Path
from threading import Event, Thread
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
    NodeControlCommandRequestCodec,
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
    WeightedRoutingControlState,
)
from control_plane_kit_server_sdk import (
    ControlPlaneInvocationContext,
    ControlPlaneVariable,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "control_plane_kit_server_sdk"
ATOMIC_MODULE = "control_plane_kit_server_sdk.atomic"
MAX_SAFE_VERSION = 2**53 - 1


class DescriptorLookalike:
    pass


class DescriptorSubclass(ControlPlaneVariableDescriptor):
    pass


class ScalarStateSubclass(ScalarControlState):
    pass


class SensitiveCandidate:
    def __repr__(self) -> str:
        return "authorization: Bearer candidate-secret"


class ExplodingReprCandidate:
    def __repr__(self) -> str:
        raise AssertionError("candidate repr must not be evaluated")


class BlockingEqualityText(str):
    def __new__(
        cls,
        value: str,
        entered: Event,
        release: Event,
        *,
        result: bool = False,
        error: Exception | None = None,
    ) -> BlockingEqualityText:
        instance = super().__new__(cls, value)
        instance.entered = entered
        instance.release = release
        instance.result = result
        instance.error = error
        return instance

    def __eq__(self, other: object) -> bool:
        self.entered.set()
        if not self.release.wait(3):
            raise AssertionError("equality release timed out")
        if self.error is not None:
            raise self.error
        return self.result

    __hash__ = str.__hash__


class ExplodingEqualityText(str):
    def __eq__(self, other: object) -> bool:
        raise AssertionError("candidate equality must not be evaluated")

    __hash__ = str.__hash__


def _reference(
    role: NodeControlGraphReferenceRole,
    value: str,
) -> NodeControlGraphReference:
    return NodeControlGraphReference(role, value)


def _target() -> NodeControlTarget:
    return NodeControlTarget(
        workspace_id=_reference(
            NodeControlGraphReferenceRole.WORKSPACE,
            "workspace-1",
        ),
        graph_revision=_reference(
            NodeControlGraphReferenceRole.GRAPH_REVISION,
            "revision-7",
        ),
        node_id=_reference(NodeControlGraphReferenceRole.NODE, "router"),
        provider_socket_name=_reference(
            NodeControlGraphReferenceRole.PROVIDER_SOCKET,
            "control",
        ),
    )


def _state_and_codecs(
    kind: ControlPlaneVariableKind,
) -> tuple[
    ScalarControlState | MapControlState | WeightedRoutingControlState,
    ControlPlaneStateCodec,
    ControlPlaneCommandCodec,
]:
    if kind is ControlPlaneVariableKind.SCALAR:
        return (
            ScalarControlState("target-a"),
            ControlPlaneStateCodec.SCALAR_V1,
            ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
        )
    if kind is ControlPlaneVariableKind.MAP:
        return (
            MapControlState((("active", "target-a"),)),
            ControlPlaneStateCodec.MAP_V1,
            ControlPlaneCommandCodec.REPLACE_MAP_V1,
        )
    target = _reference(NodeControlGraphReferenceRole.TARGET, "target-a")
    return (
        WeightedRoutingControlState(
            targets=(target,),
            weights=((target, 1.0),),
        ),
        ControlPlaneStateCodec.WEIGHTED_ROUTING_V1,
        ControlPlaneCommandCodec.REPLACE_WEIGHTED_ROUTING_V1,
    )


def _descriptor(
    kind: ControlPlaneVariableKind = ControlPlaneVariableKind.SCALAR,
    *,
    variable: str = "routing",
) -> ControlPlaneVariableDescriptor:
    _, state_codec, command_codec = _state_and_codecs(kind)
    return ControlPlaneVariableDescriptor(
        variable_name=_reference(
            NodeControlGraphReferenceRole.VARIABLE,
            variable,
        ),
        kind=kind,
        state_codec=state_codec,
        operation_contracts=(
            ControlPlaneVariableOperationContract(
                operation=NodeControlOperation.READ_STATE,
                command_codec=None,
                result_codec=ControlPlaneResultCodec.STATE_V1,
            ),
            ControlPlaneVariableOperationContract(
                operation=NodeControlOperation.APPLY_COMMAND,
                command_codec=command_codec,
                result_codec=ControlPlaneResultCodec.TRANSITION_V1,
            ),
        ),
    )


def _read_request(
    *,
    variable: str = "routing",
    request_id: str = "request-read-1",
) -> NodeControlCommandRequest:
    return NodeControlCommandRequest(
        target=_target(),
        variable_name=_reference(NodeControlGraphReferenceRole.VARIABLE, variable),
        operation=NodeControlOperation.READ_STATE,
        request_id=request_id,
        idempotency_key=f"{request_id}-key",
    )


def _apply_request(
    state: ScalarControlState | MapControlState | WeightedRoutingControlState,
    *,
    expected_version: int,
    variable: str = "routing",
    request_id: str = "request-apply-1",
) -> NodeControlCommandRequest:
    if type(state) is ScalarControlState:
        codec = ControlPlaneCommandCodec.REPLACE_SCALAR_V1
    elif type(state) is MapControlState:
        codec = ControlPlaneCommandCodec.REPLACE_MAP_V1
    else:
        codec = ControlPlaneCommandCodec.REPLACE_WEIGHTED_ROUTING_V1
    return NodeControlCommandRequest(
        target=_target(),
        variable_name=_reference(NodeControlGraphReferenceRole.VARIABLE, variable),
        operation=NodeControlOperation.APPLY_COMMAND,
        request_id=request_id,
        idempotency_key=f"{request_id}-key",
        command_codec=codec,
        precondition=ControlPlaneTransitionPrecondition(expected_version),
        payload=NodeControlPayload(codec=codec, state=state),
    )


class AtomicControlPlaneVariableTests(unittest.TestCase):
    def _atomic_type(self) -> type:
        specification = importlib.util.find_spec(ATOMIC_MODULE)
        self.assertIsNotNone(
            specification,
            "missing atomic module: control_plane_kit_server_sdk.atomic",
        )
        module = importlib.import_module(ATOMIC_MODULE)
        atomic_type = getattr(module, "AtomicControlPlaneVariable", None)
        self.assertIsNotNone(
            atomic_type,
            "missing public AtomicControlPlaneVariable",
        )
        return atomic_type

    def _assert_round_trip(
        self,
        descriptor: ControlPlaneVariableDescriptor,
        result: object,
    ) -> None:
        codec = NodeControlResultCodec(descriptor)
        self.assertEqual(codec.decode(codec.encode(result)), result)

    def test_constructor_retains_exact_descriptor_state_and_bounded_version(self) -> None:
        atomic_type = self._atomic_type()

        for kind in ControlPlaneVariableKind:
            with self.subTest(kind=kind):
                state, _, _ = _state_and_codecs(kind)
                descriptor = _descriptor(kind)
                variable = atomic_type(descriptor, state, initial_version=7)
                self.assertIs(variable.descriptor(), descriptor)
                self.assertIsInstance(variable, ControlPlaneVariable)

                read = _read_request()
                result = variable.read(ControlPlaneInvocationContext(read))
                self.assertIsInstance(result, NodeControlReadStateSucceeded)
                self.assertIs(result.state, state)
                self.assertEqual(result.version, 7)
                self._assert_round_trip(descriptor, result)

        state, _, _ = _state_and_codecs(ControlPlaneVariableKind.SCALAR)
        result = atomic_type(_descriptor(), state).read(
            ControlPlaneInvocationContext(_read_request())
        )
        self.assertEqual(result.version, 0)

    def test_constructor_rejects_non_nominal_or_incompatible_inputs_without_repr(self) -> None:
        atomic_type = self._atomic_type()
        descriptor = _descriptor()
        scalar = ScalarControlState("target-a")
        descriptor_subclass = DescriptorSubclass(
            variable_name=descriptor.variable_name,
            kind=descriptor.kind,
            state_codec=descriptor.state_codec,
            operation_contracts=descriptor.operation_contracts,
        )

        cases = (
            (
                (DescriptorLookalike(), scalar),
                "atomic variable descriptor must be ControlPlaneVariableDescriptor",
            ),
            (
                (descriptor_subclass, scalar),
                "atomic variable descriptor must be ControlPlaneVariableDescriptor",
            ),
            (
                (descriptor, object()),
                "atomic variable state must be an exact control state",
            ),
            (
                (descriptor, ScalarStateSubclass("target-a")),
                "atomic variable state must be an exact control state",
            ),
            (
                (descriptor, MapControlState((("active", "target-a"),))),
                "atomic variable state does not match descriptor state codec",
            ),
        )
        for arguments, message in cases:
            with self.subTest(message=message):
                with self.assertRaises(TypeError) as raised:
                    atomic_type(*arguments)
                self.assertEqual(str(raised.exception), message)

        for candidate in (SensitiveCandidate(), ExplodingReprCandidate()):
            with self.subTest(candidate=type(candidate).__name__):
                with self.assertRaises(TypeError) as raised:
                    atomic_type(descriptor, candidate)
                self.assertEqual(
                    str(raised.exception),
                    "atomic variable state must be an exact control state",
                )
                self.assertNotIn("candidate-secret", str(raised.exception))

        for version in (True, -1, MAX_SAFE_VERSION + 1):
            with self.subTest(version=version):
                with self.assertRaises(ValueError) as raised:
                    atomic_type(descriptor, scalar, initial_version=version)
                self.assertEqual(
                    str(raised.exception),
                    "atomic variable initial_version must be a bounded "
                    "nonnegative integer",
                )

    def test_read_is_closed_by_operation_and_variable_and_round_trips(self) -> None:
        atomic_type = self._atomic_type()
        descriptor = _descriptor()
        variable = atomic_type(descriptor, ScalarControlState("target-a"))
        wrong_variable = _read_request(variable="other", request_id="wrong-variable")
        apply = _apply_request(
            ScalarControlState("target-b"),
            expected_version=0,
            request_id="wrong-operation",
        )

        for request in (wrong_variable, apply):
            with self.subTest(request_id=request.request_id):
                result = variable.read(ControlPlaneInvocationContext(request))
                self.assertIsInstance(result, NodeControlFailed)
                self.assertEqual(result.request_id, request.request_id)
                self.assertIs(result.operation, NodeControlOperation.READ_STATE)
                self._assert_round_trip(descriptor, result)

    def test_apply_rejects_request_source_and_dispatch_mismatches_before_state(self) -> None:
        atomic_type = self._atomic_type()
        descriptor = _descriptor()
        original = ScalarControlState("target-a")
        variable = atomic_type(descriptor, original, initial_version=4)
        valid = _apply_request(
            ScalarControlState("target-b"),
            expected_version=4,
        )
        equal_request = NodeControlCommandRequestCodec().decode(
            NodeControlCommandRequestCodec().encode(valid)
        )
        self.assertEqual(equal_request, valid)
        self.assertIsNot(equal_request, valid)

        candidates = (
            (equal_request, ControlPlaneInvocationContext(valid)),
            (SensitiveCandidate(), ControlPlaneInvocationContext(valid)),
            (ExplodingReprCandidate(), ControlPlaneInvocationContext(valid)),
            (
                _read_request(request_id="wrong-operation"),
                ControlPlaneInvocationContext(_read_request(request_id="wrong-operation")),
            ),
            (
                _apply_request(
                    ScalarControlState("target-b"),
                    expected_version=4,
                    variable="other",
                    request_id="wrong-variable",
                ),
                None,
            ),
            (
                _apply_request(
                    MapControlState((("active", "target-b"),)),
                    expected_version=4,
                    request_id="wrong-codec",
                ),
                None,
            ),
        )
        for command, context in candidates:
            if context is None:
                context = ControlPlaneInvocationContext(command)
            with self.subTest(candidate=type(command).__name__, request_id=context.request.request_id):
                result = variable.apply(command, context)
                self.assertIsInstance(result, NodeControlRejected)
                self.assertEqual(result.request_id, context.request.request_id)
                self.assertIs(result.operation, NodeControlOperation.APPLY_COMMAND)
                self.assertIs(result.evidence.code, NodeControlEvidenceCode.INVALID_COMMAND)
                self.assertNotIn("candidate-secret", repr(result))
                self._assert_round_trip(descriptor, result)

        read = variable.read(ControlPlaneInvocationContext(_read_request()))
        self.assertIs(read.state, original)
        self.assertEqual(read.version, 4)

    def test_apply_scalar_map_and_weighted_routing_transition_laws(self) -> None:
        atomic_type = self._atomic_type()

        for kind in ControlPlaneVariableKind:
            state, _, _ = _state_and_codecs(kind)
            descriptor = _descriptor(kind)
            variable = atomic_type(descriptor, state, initial_version=3)
            equal = _apply_request(state, expected_version=3, request_id=f"{kind}-equal")
            no_change = variable.apply(equal, ControlPlaneInvocationContext(equal))
            self.assertIsInstance(no_change, NodeControlTransitionSucceeded)
            self.assertEqual(no_change.version, 3)
            self.assertIs(no_change.evidence.code, NodeControlEvidenceCode.NO_CHANGE)
            self._assert_round_trip(descriptor, no_change)

            if kind is ControlPlaneVariableKind.SCALAR:
                replacement = ScalarControlState("target-b")
            elif kind is ControlPlaneVariableKind.MAP:
                replacement = MapControlState((("active", "target-b"),))
            else:
                target = _reference(NodeControlGraphReferenceRole.TARGET, "target-b")
                replacement = WeightedRoutingControlState(
                    targets=(target,),
                    weights=((target, 1.0),),
                )
            apply = _apply_request(
                replacement,
                expected_version=3,
                request_id=f"{kind}-apply",
            )
            applied = variable.apply(apply, ControlPlaneInvocationContext(apply))
            self.assertIsInstance(applied, NodeControlTransitionSucceeded)
            self.assertEqual(applied.version, 4)
            self.assertIs(applied.evidence.code, NodeControlEvidenceCode.APPLIED)
            self._assert_round_trip(descriptor, applied)

            stale = _apply_request(
                state,
                expected_version=3,
                request_id=f"{kind}-stale",
            )
            rejected = variable.apply(stale, ControlPlaneInvocationContext(stale))
            self.assertIsInstance(rejected, NodeControlRejected)
            self.assertIs(
                rejected.evidence.code,
                NodeControlEvidenceCode.PRECONDITION_FAILED,
            )
            current = variable.read(ControlPlaneInvocationContext(_read_request()))
            self.assertIs(current.state, replacement)
            self.assertEqual(current.version, 4)
            self._assert_round_trip(descriptor, rejected)

    def test_max_safe_version_allows_no_change_but_never_partial_publication(self) -> None:
        atomic_type = self._atomic_type()
        descriptor = _descriptor()
        original = ScalarControlState("target-a")
        variable = atomic_type(descriptor, original, initial_version=MAX_SAFE_VERSION)

        equal = _apply_request(original, expected_version=MAX_SAFE_VERSION)
        no_change = variable.apply(equal, ControlPlaneInvocationContext(equal))
        self.assertIsInstance(no_change, NodeControlTransitionSucceeded)
        self.assertIs(no_change.evidence.code, NodeControlEvidenceCode.NO_CHANGE)
        self.assertEqual(no_change.version, MAX_SAFE_VERSION)

        changed = _apply_request(
            ScalarControlState("target-b"),
            expected_version=MAX_SAFE_VERSION,
            request_id="version-exhausted",
        )
        failed = variable.apply(changed, ControlPlaneInvocationContext(changed))
        self.assertIsInstance(failed, NodeControlFailed)
        self.assertIs(failed.operation, NodeControlOperation.APPLY_COMMAND)
        current = variable.read(ControlPlaneInvocationContext(_read_request()))
        self.assertIs(current.state, original)
        self.assertEqual(current.version, MAX_SAFE_VERSION)

    def test_blocking_equality_runs_outside_lock_and_stale_writer_cannot_publish(self) -> None:
        atomic_type = self._atomic_type()
        descriptor = _descriptor(ControlPlaneVariableKind.MAP)
        original = MapControlState((("active", "target-a"),))
        variable = atomic_type(descriptor, original, initial_version=2)
        entered = Event()
        release = Event()
        blocked_state = MapControlState(
            (("active", BlockingEqualityText("target-b", entered, release)),)
        )
        blocked = _apply_request(blocked_state, expected_version=2, request_id="blocked")
        results: list[object] = []
        thread = Thread(
            target=lambda: results.append(
                variable.apply(blocked, ControlPlaneInvocationContext(blocked))
            )
        )
        thread.start()
        self.assertTrue(entered.wait(3), "candidate equality did not start")

        read = variable.read(ControlPlaneInvocationContext(_read_request()))
        self.assertIs(read.state, original)
        self.assertEqual(read.version, 2)

        replacement = MapControlState((("active", "target-c"),))
        competing = _apply_request(
            replacement,
            expected_version=2,
            request_id="competing",
        )
        competing_result = variable.apply(
            competing,
            ControlPlaneInvocationContext(competing),
        )
        self.assertIsInstance(competing_result, NodeControlTransitionSucceeded)
        release.set()
        thread.join(3)
        self.assertFalse(thread.is_alive(), "blocked apply did not finish")
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], NodeControlRejected)
        self.assertIs(
            results[0].evidence.code,
            NodeControlEvidenceCode.PRECONDITION_FAILED,
        )
        current = variable.read(ControlPlaneInvocationContext(_read_request()))
        self.assertIs(current.state, replacement)
        self.assertEqual(current.version, 3)

    def test_blocked_equal_candidate_cannot_publish_stale_no_change(self) -> None:
        atomic_type = self._atomic_type()
        descriptor = _descriptor(ControlPlaneVariableKind.MAP)
        original = MapControlState((("active", "target-a"),))
        variable = atomic_type(descriptor, original, initial_version=2)
        entered = Event()
        release = Event()
        blocked_state = MapControlState(
            (("active", BlockingEqualityText("target-a", entered, release, result=True)),)
        )
        blocked = _apply_request(blocked_state, expected_version=2, request_id="blocked-equal")
        results: list[object] = []
        thread = Thread(
            target=lambda: results.append(
                variable.apply(blocked, ControlPlaneInvocationContext(blocked))
            )
        )
        thread.start()
        self.assertTrue(entered.wait(3), "candidate equality did not start")

        replacement = MapControlState((("active", "target-c"),))
        competing = _apply_request(replacement, expected_version=2, request_id="competing")
        variable.apply(competing, ControlPlaneInvocationContext(competing))
        release.set()
        thread.join(3)
        self.assertFalse(thread.is_alive(), "blocked apply did not finish")
        self.assertIsInstance(results[0], NodeControlRejected)
        self.assertIs(
            results[0].evidence.code,
            NodeControlEvidenceCode.PRECONDITION_FAILED,
        )

    def test_equality_failure_is_bounded_and_preserves_snapshot(self) -> None:
        atomic_type = self._atomic_type()
        descriptor = _descriptor(ControlPlaneVariableKind.MAP)
        original = MapControlState((("active", "target-a"),))
        variable = atomic_type(descriptor, original, initial_version=2)
        entered = Event()
        release = Event()
        candidate = MapControlState(
            ((
                "active",
                BlockingEqualityText(
                    "candidate-secret",
                    entered,
                    release,
                    error=RuntimeError("authorization: Bearer equality-secret"),
                ),
            ),)
        )
        request = _apply_request(candidate, expected_version=2)
        results: list[object] = []
        thread = Thread(
            target=lambda: results.append(
                variable.apply(request, ControlPlaneInvocationContext(request))
            )
        )
        thread.start()
        self.assertTrue(entered.wait(3), "candidate equality did not start")
        release.set()
        thread.join(3)
        self.assertFalse(thread.is_alive(), "failed equality apply did not finish")
        self.assertIsInstance(results[0], NodeControlFailed)
        self.assertEqual(repr(results[0]), "NodeControlFailed(operation=<NodeControlOperation.APPLY_COMMAND: 'apply-command'>)")
        self.assertNotIn("equality-secret", repr(results[0]))
        current = variable.read(ControlPlaneInvocationContext(_read_request()))
        self.assertIs(current.state, original)
        self.assertEqual(current.version, 2)

    def test_identity_dispatch_and_stale_preconditions_do_not_run_state_equality(self) -> None:
        atomic_type = self._atomic_type()
        descriptor = _descriptor(ControlPlaneVariableKind.MAP)
        original = MapControlState((("active", "target-a"),))
        variable = atomic_type(descriptor, original, initial_version=2)
        hostile = MapControlState((("active", ExplodingEqualityText("target-b")),))

        mismatch = _apply_request(hostile, expected_version=2, request_id="mismatch")
        equal_copy = NodeControlCommandRequestCodec().decode(
            NodeControlCommandRequestCodec().encode(mismatch)
        )
        identity_result = variable.apply(equal_copy, ControlPlaneInvocationContext(mismatch))
        self.assertIs(identity_result.evidence.code, NodeControlEvidenceCode.INVALID_COMMAND)

        stale = _apply_request(hostile, expected_version=1, request_id="stale")
        stale_result = variable.apply(stale, ControlPlaneInvocationContext(stale))
        self.assertIs(stale_result.evidence.code, NodeControlEvidenceCode.PRECONDITION_FAILED)

        read = _read_request(request_id="dispatch")
        dispatch_result = variable.apply(read, ControlPlaneInvocationContext(read))
        self.assertIs(dispatch_result.evidence.code, NodeControlEvidenceCode.INVALID_COMMAND)

    def test_atomic_source_has_one_snapshot_publication_and_no_durable_authority(self) -> None:
        self._atomic_type()
        path = PACKAGE_ROOT / "atomic.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports: set[str] = set()
        classes: list[ast.ClassDef] = []
        snapshot_assignments = 0
        forbidden_attributes: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.ClassDef):
                classes.append(node)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                        and target.attr == "_snapshot"
                    ):
                        snapshot_assignments += 1
            elif isinstance(node, ast.Attribute) and node.attr in {
                "idempotency_key",
                "target",
                "canonical_digest",
            }:
                forbidden_attributes.add(node.attr)

        self.assertEqual(
            imports,
            {
                "__future__",
                "control_plane_kit_core",
                "control_plane_kit_server_sdk",
                "dataclasses",
                "threading",
            },
        )
        self.assertEqual(
            [value.name for value in classes],
            ["_AtomicSnapshot", "AtomicControlPlaneVariable"],
        )
        self.assertEqual(snapshot_assignments, 2, "constructor plus one publish site")
        self.assertEqual(forbidden_attributes, set())
        source = path.read_text(encoding="utf-8")
        for forbidden in ("ledger", "replay", "cache", "persist", "authenticate"):
            self.assertNotIn(forbidden, source.lower())


if __name__ == "__main__":
    unittest.main()
