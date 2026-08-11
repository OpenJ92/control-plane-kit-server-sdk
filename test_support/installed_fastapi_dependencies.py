from __future__ import annotations

from importlib.metadata import version
import sys


def _reject() -> int:
    print("fastapi dependencies are not accepted", file=sys.stderr)
    return 2


def main() -> int:
    try:
        import control_plane_kit_server_sdk
    except Exception:
        return _reject()

    if not (
        "fastapi" not in sys.modules
        and "starlette" not in sys.modules
        and "anyio" not in sys.modules
        and "jwt" not in sys.modules
        and "cryptography" not in sys.modules
    ):
        return _reject()

    try:
        accepted = (
            version("PyJWT") == "2.13.0"
            and version("cryptography") == "50.0.0"
            and version("fastapi") == "0.141.1"
        )
    except Exception:
        return _reject()
    if not accepted:
        return _reject()

    try:
        import control_plane_kit_server_sdk._fastapi_variable_routes
    except Exception:
        return _reject()

    print("fastapi dependencies import ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
