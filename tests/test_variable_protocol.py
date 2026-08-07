from __future__ import annotations

import ast
import importlib
import importlib.util
from pathlib import Path
from typing import get_args, get_type_hints
import unittest

from control_plane_kit_core import (
    ControlPlaneCommandCodec,
    ControlPlaneResultCodec,
    ControlPlaneStateCodec,
    ControlPlaneTransitionPrecondition,
    ControlPlaneVariableDescriptor,
    ControlPlaneVariableKind,
    ControlPlaneVariableOperationContract,
    NodeControlCommandRequest,
    NodeControlCommandRequestCodec,
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
from control_plane_kit_server_sdk import ControlPlaneInvocationContext


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "control_plane_kit_server_sdk"
PROTOCOL_MODULE = "control_plane_kit_server_sdk.protocol"


ReadResult = NodeControlReadStateSucceeded | NodeControlRejected | NodeControlFailed
TransitionResult = (
    NodeControlTransitionSucceeded | NodeControlRejected | NodeControlFailed
)


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


def _variable_descriptor() -> ControlPlaneVariableDescriptor:
    return ControlPlaneVariableDescriptor(
        variable_name=_reference(
            NodeControlGraphReferenceRole.VARIABLE,
            "routing",
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


def _read_request(request_id: str = "request-read-1") -> NodeControlCommandRequest:
    return NodeControlCommandRequest(
        target=_target(),
        variable_name=_reference(
            NodeControlGraphReferenceRole.VARIABLE,
            "routing",
        ),
        operation=NodeControlOperation.READ_STATE,
        request_id=request_id,
        idempotency_key="routing-read-1",
    )


def _apply_request(request_id: str = "request-apply-1") -> NodeControlCommandRequest:
    return NodeControlCommandRequest(
        target=_target(),
        variable_name=_reference(
            NodeControlGraphReferenceRole.VARIABLE,
            "routing",
        ),
        operation=NodeControlOperation.APPLY_COMMAND,
        request_id=request_id,
        idempotency_key="routing-apply-1",
        command_codec=ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
        precondition=ControlPlaneTransitionPrecondition(expected_version=4),
        payload=NodeControlPayload(
            codec=ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
            state=ScalarControlState("target-b"),
        ),
    )


class FakeDurableService:
    """Test-owned durable service; the SDK owns none of these facts."""

    def __init__(self, descriptor: ControlPlaneVariableDescriptor) -> None:
        self.variable_descriptor = descriptor
        self.state = ScalarControlState("target-a")
        self.version = 4
        self.ledger: tuple[str, ...] = ()
        self.commits = 0

    def read(self, request_id: str) -> NodeControlReadStateSucceeded:
        return NodeControlReadStateSucceeded(
            request_id=request_id,
            state_codec=self.variable_descriptor.state_codec,
            version=self.version,
            state=self.state,
        )

    def replace(self, request: NodeControlCommandRequest) -> NodeControlTransitionSucceeded:
        assert request.payload is not None
        self.state = request.payload.state
        self.version += 1
        self.ledger = (*self.ledger, request.idempotency_key)
        self.commits += 1
        return NodeControlTransitionSucceeded(
            request_id=request.request_id,
            version=self.version,
            evidence=NodeControlEvidence(NodeControlEvidenceCode.APPLIED),
        )


class FakeDurableVariable:
    """Independent adapter proving structural conformance without inheritance."""

    def __init__(self, service: FakeDurableService) -> None:
        self.service = service

    def descriptor(self) -> ControlPlaneVariableDescriptor:
        return self.service.variable_descriptor

    def read(self, context: ControlPlaneInvocationContext) -> ReadResult:
        return self.service.read(context.request.request_id)

    def apply(
        self,
        command: NodeControlCommandRequest,
        context: ControlPlaneInvocationContext,
    ) -> TransitionResult:
        if command is not context.request:
            return NodeControlRejected(
                request_id=context.request.request_id,
                operation=NodeControlOperation.APPLY_COMMAND,
                evidence=NodeControlEvidence(NodeControlEvidenceCode.INVALID_COMMAND),
            )
        return self.service.replace(context.request)


class MissingDescriptor:
    def read(self, context: ControlPlaneInvocationContext) -> ReadResult:
        return NodeControlFailed(context.request.request_id, NodeControlOperation.READ_STATE)

    def apply(
        self,
        command: NodeControlCommandRequest,
        context: ControlPlaneInvocationContext,
    ) -> TransitionResult:
        return NodeControlFailed(
            context.request.request_id,
            NodeControlOperation.APPLY_COMMAND,
        )


class MissingRead:
    def descriptor(self) -> ControlPlaneVariableDescriptor:
        return _variable_descriptor()

    def apply(
        self,
        command: NodeControlCommandRequest,
        context: ControlPlaneInvocationContext,
    ) -> TransitionResult:
        return NodeControlFailed(
            context.request.request_id,
            NodeControlOperation.APPLY_COMMAND,
        )


class MissingApply:
    def descriptor(self) -> ControlPlaneVariableDescriptor:
        return _variable_descriptor()

    def read(self, context: ControlPlaneInvocationContext) -> ReadResult:
        return NodeControlFailed(context.request.request_id, NodeControlOperation.READ_STATE)


class WrongSignatures:
    def descriptor(self, extra: object) -> None:
        return None

    def read(self) -> None:
        return None

    def apply(self) -> None:
        return None


class SensitiveCandidate:
    def __repr__(self) -> str:
        return "authorization: Bearer candidate-secret"


class ExplodingReprCandidate:
    def __repr__(self) -> str:
        raise AssertionError("candidate repr must not be evaluated")


class VariableProtocolTests(unittest.TestCase):
    def _protocol_type(self) -> type:
        specification = importlib.util.find_spec(PROTOCOL_MODULE)
        self.assertIsNotNone(
            specification,
            "missing protocol module: control_plane_kit_server_sdk.protocol",
        )
        module = importlib.import_module(PROTOCOL_MODULE)
        protocol_type = getattr(module, "ControlPlaneVariable", None)
        self.assertIsNotNone(protocol_type, "missing public ControlPlaneVariable")
        return protocol_type

    def test_protocol_declares_exact_generic_variance_and_annotations(self) -> None:
        protocol_type = self._protocol_type()
        parameters = protocol_type.__parameters__

        self.assertEqual(len(parameters), 3)
        read_result, command, transition_result = parameters
        self.assertTrue(read_result.__covariant__)
        self.assertFalse(read_result.__contravariant__)
        self.assertIs(command.__bound__, NodeControlCommandRequest)
        self.assertTrue(command.__contravariant__)
        self.assertFalse(command.__covariant__)
        self.assertTrue(transition_result.__covariant__)
        self.assertFalse(transition_result.__contravariant__)
        self.assertEqual(
            set(get_args(read_result.__bound__)),
            {NodeControlReadStateSucceeded, NodeControlRejected, NodeControlFailed},
        )
        self.assertEqual(
            set(get_args(transition_result.__bound__)),
            {NodeControlTransitionSucceeded, NodeControlRejected, NodeControlFailed},
        )

        descriptor_hints = get_type_hints(protocol_type.descriptor)
        read_hints = get_type_hints(protocol_type.read)
        apply_hints = get_type_hints(protocol_type.apply)
        self.assertIs(descriptor_hints["return"], ControlPlaneVariableDescriptor)
        self.assertIs(read_hints["context"], ControlPlaneInvocationContext)
        self.assertIs(read_hints["return"], read_result)
        self.assertIs(apply_hints["command"], command)
        self.assertIs(apply_hints["context"], ControlPlaneInvocationContext)
        self.assertIs(apply_hints["return"], transition_result)

    def test_runtime_protocol_checks_member_presence_only(self) -> None:
        protocol_type = self._protocol_type()
        fake = FakeDurableVariable(FakeDurableService(_variable_descriptor()))

        self.assertIsInstance(fake, protocol_type)
        for candidate in (MissingDescriptor(), MissingRead(), MissingApply()):
            with self.subTest(candidate=type(candidate).__name__):
                self.assertNotIsInstance(candidate, protocol_type)
        self.assertIsInstance(
            WrongSignatures(),
            protocol_type,
            "runtime protocol checking must not be represented as signature proof",
        )

    def test_fake_durable_owner_preserves_descriptor_and_core_result_algebra(self) -> None:
        protocol_type = self._protocol_type()
        descriptor = _variable_descriptor()
        service = FakeDurableService(descriptor)
        variable = FakeDurableVariable(service)

        self.assertIsInstance(variable, protocol_type)
        self.assertIs(variable.descriptor(), descriptor)
        codec = NodeControlResultCodec(descriptor)

        read_request = _read_request()
        read_result = variable.read(ControlPlaneInvocationContext(read_request))
        self.assertEqual(codec.encode(read_result)["codec"], "control.state.v1")

        apply_request = _apply_request()
        transition_result = variable.apply(
            apply_request,
            ControlPlaneInvocationContext(apply_request),
        )
        self.assertEqual(
            codec.encode(transition_result)["codec"],
            "control.transition.v1",
        )
        self.assertEqual(service.commits, 1)
        self.assertEqual(service.ledger, (apply_request.idempotency_key,))

        for result in (
            NodeControlRejected(
                request_id=read_request.request_id,
                operation=NodeControlOperation.READ_STATE,
                evidence=NodeControlEvidence(NodeControlEvidenceCode.NOT_AUTHORIZED),
            ),
            NodeControlFailed(
                request_id=read_request.request_id,
                operation=NodeControlOperation.READ_STATE,
            ),
            NodeControlRejected(
                request_id=apply_request.request_id,
                operation=NodeControlOperation.APPLY_COMMAND,
                evidence=NodeControlEvidence(
                    NodeControlEvidenceCode.PRECONDITION_FAILED
                ),
            ),
            NodeControlFailed(
                request_id=apply_request.request_id,
                operation=NodeControlOperation.APPLY_COMMAND,
            ),
        ):
            with self.subTest(result=type(result).__name__, operation=result.operation):
                self.assertEqual(
                    codec.encode(result)["operation"],
                    result.operation.value,
                )

    def test_apply_requires_exact_context_request_without_rendering_candidate(self) -> None:
        service = FakeDurableService(_variable_descriptor())
        variable = FakeDurableVariable(service)
        request = _apply_request()
        context = ControlPlaneInvocationContext(request)
        equal_request = NodeControlCommandRequestCodec().decode(
            NodeControlCommandRequestCodec().encode(request)
        )
        self.assertEqual(equal_request, request)
        self.assertIsNot(equal_request, request)

        for candidate in (
            equal_request,
            SensitiveCandidate(),
            ExplodingReprCandidate(),
        ):
            with self.subTest(candidate=type(candidate).__name__):
                result = variable.apply(candidate, context)
                self.assertIsInstance(result, NodeControlRejected)
                self.assertEqual(result.request_id, context.request.request_id)
                self.assertIs(result.operation, NodeControlOperation.APPLY_COMMAND)
                self.assertIs(
                    result.evidence.code,
                    NodeControlEvidenceCode.INVALID_COMMAND,
                )
                self.assertNotIn("candidate-secret", repr(result))

        self.assertEqual(service.version, 4)
        self.assertEqual(service.state, ScalarControlState("target-a"))
        self.assertEqual(service.ledger, ())
        self.assertEqual(service.commits, 0)

    def test_protocol_source_shape_is_structurally_bounded(self) -> None:
        path = PACKAGE_ROOT / "protocol.py"
        self.assertTrue(path.is_file(), "missing protocol source module")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        import_roots: set[str] = set()
        classes: list[ast.ClassDef] = []
        functions: list[str] = []
        assignments: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                import_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                import_roots.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.ClassDef):
                classes.append(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
            elif isinstance(node, ast.Assign):
                assignments.extend(
                    target.id for target in node.targets if isinstance(target, ast.Name)
                )
        self.assertEqual(
            import_roots,
            {
                "__future__",
                "control_plane_kit_core",
                "control_plane_kit_server_sdk",
                "typing",
            },
        )
        self.assertEqual(functions, [])
        self.assertEqual(
            assignments,
            [
                "_ReadResultT_co",
                "_CommandT_contra",
                "_TransitionResultT_co",
                "__all__",
            ],
        )
        self.assertEqual(
            [value.name for value in classes],
            ["ControlPlaneVariable"],
        )
        self.assertEqual(
            [
                node.name
                for node in classes[0].body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ],
            ["descriptor", "read", "apply"],
        )

    def test_pep561_marker_is_explicit_and_empty(self) -> None:
        marker = PACKAGE_ROOT / "py.typed"
        self.assertTrue(marker.is_file(), "missing package-local py.typed marker")
        self.assertEqual(marker.read_bytes(), b"")

    def test_readme_and_decision_state_protocol_proof_boundaries(self) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        decision_path = REPOSITORY_ROOT / "docs" / "decisions" / "0006-variable-protocol.md"
        self.assertTrue(decision_path.is_file(), "missing variable-protocol decision")
        decision = decision_path.read_text(encoding="utf-8")

        for text in (
            "ControlPlaneVariable",
            "command is context.request",
            "member presence only",
            "py.typed",
            "test-owned",
        ):
            with self.subTest(document="README", text=text):
                self.assertIn(text, readme)
            with self.subTest(document="decision", text=text):
                self.assertIn(text, decision)


if __name__ == "__main__":
    unittest.main()
