"""Closed synchronous workload-health interpretation, independent of HTTP hosts."""
from __future__ import annotations

from dataclasses import dataclass, field
from inspect import isasyncgenfunction, iscoroutinefunction, signature
from types import CoroutineType
from typing import Callable

from control_plane_kit_core import (
    NodeControlGraphReference,
    NodeControlGraphReferenceRole,
    NodeControlTarget,
    NodeHealthReadKind,
    NodeHealthReadOutcome,
    NodeHealthReadResult,
    WorkloadNodeControlSurfaceDeclaration,
    WorkloadNodeControlSurfaceDeclarationProfile,
)
from control_plane_kit_server_sdk.verification import Ed25519WorkloadNodeHealthReadVerifier


class WorkloadNodeHealthReadDispatchError(ValueError):
    """A callback failed to produce a closed semantic observation."""

    __slots__ = ()


def _require_sync_callback(callback: object) -> None:
    if not callable(callback):
        raise TypeError
    call = getattr(callback, "__call__", None)
    if any(predicate(value) for predicate in (iscoroutinefunction, isasyncgenfunction)
           for value in (callback, call)):
        raise TypeError
    # Validate no-argument invocation without executing workload code.
    signature(callback).bind()


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkloadNodeHealthReadDispatcher:
    """Capture trusted local composition and admit before each protected read."""

    target: NodeControlTarget = field(repr=False)
    runtime_id: NodeControlGraphReference = field(repr=False)
    declaration: WorkloadNodeControlSurfaceDeclaration = field(repr=False)
    verifier: Ed25519WorkloadNodeHealthReadVerifier = field(repr=False)
    liveness: Callable[[], NodeHealthReadOutcome] | None = field(default=None, repr=False)
    readiness: Callable[[], NodeHealthReadOutcome] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        accepted = False
        try:
            if (
                type(self.target) is not NodeControlTarget
                or type(self.runtime_id) is not NodeControlGraphReference
                or self.runtime_id.role is not NodeControlGraphReferenceRole.RUNTIME
                or type(self.declaration) is not WorkloadNodeControlSurfaceDeclaration
                or self.declaration.profile is not WorkloadNodeControlSurfaceDeclarationProfile.V2
                or type(self.verifier) is not Ed25519WorkloadNodeHealthReadVerifier
                or self.target.provider_socket_name != self.declaration.surface.provider_socket_name
            ):
                raise ValueError
            for kind, callback in (
                (NodeHealthReadKind.LIVENESS, self.liveness),
                (NodeHealthReadKind.READINESS, self.readiness),
            ):
                if (callback is not None) != (kind in self.declaration.surface.health_reads):
                    raise ValueError
                if callback is not None:
                    _require_sync_callback(callback)
            accepted = True
        except Exception:
            pass
        if not accepted:
            raise ValueError("workload health-read dispatcher configuration is invalid")

    def read(
        self, credential: bytes, *, route_kind: NodeHealthReadKind, candidate: None,
    ) -> NodeHealthReadResult:
        request = self.verifier.admit(
            credential, route_kind=route_kind, candidate=candidate,
            expected_target=self.target, expected_runtime_id=self.runtime_id,
            expected_declaration=self.declaration,
        )
        try:
            callback = self.liveness if request.kind is NodeHealthReadKind.LIVENESS else self.readiness
            outcome = callback()
            if type(outcome) is not NodeHealthReadOutcome:
                # Do not execute an accidentally returned coroutine or let its
                # unawaited warning expose callback implementation details.
                if type(outcome) is CoroutineType:
                    outcome.close()
                raise TypeError
            return NodeHealthReadResult(request, self.declaration, outcome)
        except Exception:
            pass
        raise WorkloadNodeHealthReadDispatchError("workload health read failed")


__all__ = ["WorkloadNodeHealthReadDispatcher", "WorkloadNodeHealthReadDispatchError"]
