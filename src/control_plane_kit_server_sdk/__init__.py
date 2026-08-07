"""Framework-neutral workload node-control SDK boundary."""

from control_plane_kit_server_sdk.atomic import AtomicControlPlaneVariable
from control_plane_kit_server_sdk.context import ControlPlaneInvocationContext
from control_plane_kit_server_sdk.protocol import ControlPlaneVariable


__version__ = "0.1.0"

__all__ = [
    "AtomicControlPlaneVariable",
    "ControlPlaneInvocationContext",
    "ControlPlaneVariable",
    "__version__",
]
