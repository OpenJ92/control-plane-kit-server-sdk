"""Neutral invocation context for an outer-admitted node-control request."""

from __future__ import annotations

from dataclasses import dataclass, field

from control_plane_kit_core import ReceiverNodeControlRequest


@dataclass(frozen=True, slots=True)
class ControlPlaneInvocationContext:
    """Retain the exact request supplied by an outer admission adapter."""

    request: ReceiverNodeControlRequest = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.request) is not ReceiverNodeControlRequest:
            raise TypeError(
                "control-plane invocation request must be "
                "ReceiverNodeControlRequest"
            )


__all__ = ["ControlPlaneInvocationContext"]
