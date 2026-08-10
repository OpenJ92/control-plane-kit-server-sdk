from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass
import importlib
import importlib.util
from pathlib import Path
from typing import get_type_hints
import unittest

from control_plane_kit_core.node_control import (
    ControlPlaneCommandCodec,
    ControlPlaneTransitionPrecondition,
    NodeControlCommandRequest,
    NodeControlGraphReference,
    NodeControlGraphReferenceRole,
    NodeControlOperation,
    NodeControlPayload,
    NodeControlTarget,
    ScalarControlState,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "control_plane_kit_server_sdk"
CONTEXT_MODULE = "control_plane_kit_server_sdk.context"


class RequestLookalike:
    def __init__(self, request: NodeControlCommandRequest) -> None:
        self.request_id = request.request_id
        self.target = request.target


class RequestSubclass(NodeControlCommandRequest):
    pass


class SensitiveCandidate:
    def __repr__(self) -> str:
        return "authorization: Bearer candidate-secret"


class ExplodingReprCandidate:
    def __repr__(self) -> str:
        raise AssertionError("candidate repr must not be evaluated")


class InvocationContextTests(unittest.TestCase):
    def _context_type(self) -> type:
        specification = importlib.util.find_spec(CONTEXT_MODULE)
        self.assertIsNotNone(
            specification,
            "missing context module: control_plane_kit_server_sdk.context",
        )
        module = importlib.import_module(CONTEXT_MODULE)
        context_type = getattr(module, "ControlPlaneInvocationContext", None)
        self.assertIsNotNone(
            context_type,
            "missing public context: ControlPlaneInvocationContext",
        )
        return context_type

    def _reference(
        self,
        role: NodeControlGraphReferenceRole,
        value: str,
    ) -> NodeControlGraphReference:
        return NodeControlGraphReference(role, value)

    def _target(self) -> NodeControlTarget:
        return NodeControlTarget(
            workspace_id=self._reference(
                NodeControlGraphReferenceRole.WORKSPACE,
                "workspace-1",
            ),
            graph_revision=self._reference(
                NodeControlGraphReferenceRole.GRAPH_REVISION,
                "revision-7",
            ),
            node_id=self._reference(NodeControlGraphReferenceRole.NODE, "router"),
            provider_socket_name=self._reference(
                NodeControlGraphReferenceRole.PROVIDER_SOCKET,
                "control",
            ),
        )

    def _read_request(self) -> NodeControlCommandRequest:
        return NodeControlCommandRequest(
            target=self._target(),
            variable_name=self._reference(
                NodeControlGraphReferenceRole.VARIABLE,
                "routing",
            ),
            operation=NodeControlOperation.READ_STATE,
            request_id="request-read-1",
            idempotency_key="routing-read-1",
        )

    def _apply_request(self) -> NodeControlCommandRequest:
        return NodeControlCommandRequest(
            target=self._target(),
            variable_name=self._reference(
                NodeControlGraphReferenceRole.VARIABLE,
                "routing",
            ),
            operation=NodeControlOperation.APPLY_COMMAND,
            request_id="request-apply-1",
            idempotency_key="routing-apply-1",
            command_codec=ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
            precondition=ControlPlaneTransitionPrecondition(expected_version=3),
            payload=NodeControlPayload(
                codec=ControlPlaneCommandCodec.REPLACE_SCALAR_V1,
                state=ScalarControlState("target-a"),
            ),
        )

    def test_exact_core_read_and_apply_requests_are_retained(self) -> None:
        context_type = self._context_type()

        for request in (self._read_request(), self._apply_request()):
            with self.subTest(operation=request.operation):
                context = context_type(request)
                self.assertIs(context.request, request)
                self.assertEqual(repr(context), "ControlPlaneInvocationContext()")

    def test_plain_lookalike_and_subclass_requests_are_rejected(self) -> None:
        context_type = self._context_type()
        request = self._read_request()
        subclass = RequestSubclass(
            target=request.target,
            variable_name=request.variable_name,
            operation=request.operation,
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
        )

        for candidate in (object(), RequestLookalike(request), subclass):
            with self.subTest(candidate_type=type(candidate).__name__):
                with self.assertRaisesRegex(
                    TypeError,
                    "^control-plane invocation request must be "
                    "NodeControlCommandRequest$",
                ):
                    context_type(candidate)

    def test_rejected_candidate_repr_is_never_evaluated_or_rendered(self) -> None:
        context_type = self._context_type()

        for candidate in (SensitiveCandidate(), ExplodingReprCandidate()):
            with self.subTest(candidate_type=type(candidate).__name__):
                with self.assertRaises(TypeError) as raised:
                    context_type(candidate)
                self.assertEqual(
                    str(raised.exception),
                    "control-plane invocation request must be "
                    "NodeControlCommandRequest",
                )
                self.assertNotIn("candidate-secret", str(raised.exception))

    def test_context_is_one_frozen_slotted_repr_hidden_field(self) -> None:
        context_type = self._context_type()
        request = self._apply_request()
        context = context_type(request)

        self.assertTrue(is_dataclass(context_type))
        self.assertTrue(context_type.__dataclass_params__.frozen)
        self.assertEqual(context_type.__slots__, ("request",))
        self.assertFalse(hasattr(context, "__dict__"))
        self.assertEqual(
            tuple((value.name, value.repr) for value in fields(context_type)),
            (("request", False),),
        )
        self.assertIs(
            get_type_hints(context_type)["request"],
            NodeControlCommandRequest,
        )
        with self.assertRaises((FrozenInstanceError, TypeError, AttributeError)):
            context.request = self._read_request()
        with self.assertRaises((FrozenInstanceError, TypeError, AttributeError)):
            context.authenticated = True

    def test_context_has_no_wire_authority_or_mutable_storage_surface(self) -> None:
        context_type = self._context_type()
        context = context_type(self._apply_request())

        for name in (
            "authenticated",
            "admitted",
            "provenance",
            "grant",
            "signature",
            "key",
            "headers",
            "body",
            "descriptor",
            "codec",
            "encode",
            "decode",
            "canonical_bytes",
            "canonical_digest",
            "registry",
            "replay",
            "lock",
            "storage",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(context, name), name)

    def test_context_module_imports_and_members_are_structurally_bounded(self) -> None:
        path = PACKAGE_ROOT / "context.py"
        self.assertTrue(path.is_file(), "missing context source module")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        import_roots: set[str] = set()
        classes: list[ast.ClassDef] = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                import_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                import_roots.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.ClassDef):
                classes.append(node)
        self.assertEqual(
            import_roots,
            {"__future__", "control_plane_kit_core", "dataclasses"},
        )
        self.assertEqual(
            [value.name for value in classes],
            ["ControlPlaneInvocationContext"],
        )
        context_class = classes[0]
        field_names = [
            node.target.id
            for node in context_class.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
        ]
        method_names = [
            node.name
            for node in context_class.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        self.assertEqual(field_names, ["request"])
        self.assertEqual(method_names, ["__post_init__"])

    def test_readme_and_decision_state_the_neutral_trust_boundary(self) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        decision_path = (
            REPOSITORY_ROOT
            / "docs"
            / "decisions"
            / "0005-invocation-context.md"
        )
        self.assertTrue(decision_path.is_file(), "missing invocation-context decision")
        decision = decision_path.read_text(encoding="utf-8")

        for text in (
            "ControlPlaneInvocationContext",
            "does not authenticate",
            "does not prove graph membership",
        ):
            with self.subTest(document="README", text=text):
                self.assertIn(text, readme)
            with self.subTest(document="decision", text=text):
                self.assertIn(text, decision)


if __name__ == "__main__":
    unittest.main()
