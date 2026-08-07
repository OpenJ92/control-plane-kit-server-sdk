"""Neutral invocation context for an outer-admitted node-control request."""

from __future__ import annotations

from dataclasses import dataclass, field

from control_plane_kit_core import NodeControlCommandRequest


@dataclass(frozen=True, slots=True)
class ControlPlaneInvocationContext:
    """Retain the exact request supplied by an outer admission adapter."""

    request: NodeControlCommandRequest = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.request) is not NodeControlCommandRequest:
            raise TypeError(
                "control-plane invocation request must be "
                "NodeControlCommandRequest"
            )


__all__ = ["ControlPlaneInvocationContext"]
