from __future__ import annotations

import sys

import control_plane_kit_server_sdk


if control_plane_kit_server_sdk.__version__ != "0.1.0":
    raise SystemExit("unexpected installed SDK version")

eager_dependencies = tuple(
    name for name in ("control_plane_kit_core", "fastapi") if name in sys.modules
)
if eager_dependencies:
    raise SystemExit(f"unexpected eager import: {eager_dependencies}")

print("control-plane-kit-server-sdk import ok")
