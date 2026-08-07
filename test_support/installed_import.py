from __future__ import annotations

from importlib import resources
import sys

import control_plane_kit_server_sdk


if control_plane_kit_server_sdk.__version__ != "0.1.0":
    raise SystemExit("unexpected installed SDK version")
if control_plane_kit_server_sdk.__all__ != [
    "AtomicControlPlaneVariable",
    "ControlPlaneInvocationContext",
    "ControlPlaneVariable",
    "__version__",
]:
    raise SystemExit("unexpected installed SDK exports")
if (
    control_plane_kit_server_sdk.AtomicControlPlaneVariable.__module__
    != "control_plane_kit_server_sdk.atomic"
):
    raise SystemExit("unexpected installed SDK atomic variable owner")
if (
    control_plane_kit_server_sdk.ControlPlaneInvocationContext.__module__
    != "control_plane_kit_server_sdk.context"
):
    raise SystemExit("unexpected installed SDK context owner")
if (
    control_plane_kit_server_sdk.ControlPlaneVariable.__module__
    != "control_plane_kit_server_sdk.protocol"
):
    raise SystemExit("unexpected installed SDK protocol owner")

type_marker = resources.files("control_plane_kit_server_sdk").joinpath("py.typed")
if not type_marker.is_file() or type_marker.read_bytes() != b"":
    raise SystemExit("installed SDK type marker is missing or malformed")

forbidden_dependencies = tuple(
    name
    for name in (
        "control_plane_kit_operations",
        "control_plane_kit_interpreters",
        "control_plane_kit_secrets",
        "control_plane_kit_servers",
        "fastapi",
        "psycopg",
        "docker",
        "cloudflare",
        "cryptography",
        "jwt",
    )
    if name in sys.modules
)
if forbidden_dependencies:
    raise SystemExit(f"unexpected forbidden import: {forbidden_dependencies}")
if "control_plane_kit_core" not in sys.modules:
    raise SystemExit("installed context did not load the pinned core contract")

print("control-plane-kit-server-sdk import ok")
