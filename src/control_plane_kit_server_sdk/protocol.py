"""Structural extension protocol for workload-owned control variables."""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from control_plane_kit_core import (
    ControlPlaneVariableDescriptor,
    NodeControlCommandRequest,
    NodeControlFailed,
    NodeControlReadStateSucceeded,
    NodeControlRejected,
    NodeControlTransitionSucceeded,
)
from control_plane_kit_server_sdk.context import ControlPlaneInvocationContext


_ReadResultT_co = TypeVar(
    "_ReadResultT_co",
    bound=NodeControlReadStateSucceeded | NodeControlRejected | NodeControlFailed,
    covariant=True,
)
_CommandT_contra = TypeVar(
    "_CommandT_contra",
    bound=NodeControlCommandRequest,
    contravariant=True,
)
_TransitionResultT_co = TypeVar(
    "_TransitionResultT_co",
    bound=NodeControlTransitionSucceeded | NodeControlRejected | NodeControlFailed,
    covariant=True,
)


@runtime_checkable
class ControlPlaneVariable(
    Protocol[_ReadResultT_co, _CommandT_contra, _TransitionResultT_co]
):
    """A typed variable implemented by its process-local or durable owner.

    Runtime conformance checks member presence only. Implementations must check
    ``command is context.request`` before apply work and reject a mismatch with
    context-keyed, closed ``INVALID_COMMAND`` evidence without rendering the
    candidate.
    """

    def descriptor(self) -> ControlPlaneVariableDescriptor: ...

    def read(self, context: ControlPlaneInvocationContext) -> _ReadResultT_co: ...

    def apply(
        self,
        command: _CommandT_contra,
        context: ControlPlaneInvocationContext,
    ) -> _TransitionResultT_co: ...


__all__ = ["ControlPlaneVariable"]
