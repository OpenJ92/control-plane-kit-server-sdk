from __future__ import annotations

import sys

import control_plane_kit_server_sdk


if control_plane_kit_server_sdk.__version__ != "0.1.0":
    raise SystemExit("unexpected installed SDK version")
if control_plane_kit_server_sdk.__all__ != [
    "ControlPlaneInvocationContext",
    "__version__",
]:
    raise SystemExit("unexpected installed SDK exports")
if (
    control_plane_kit_server_sdk.ControlPlaneInvocationContext.__module__
    != "control_plane_kit_server_sdk.context"
):
    raise SystemExit("unexpected installed SDK context owner")

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
