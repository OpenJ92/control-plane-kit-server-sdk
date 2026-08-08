from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
import sys


def _reject() -> int:
    print("verification dependencies are not accepted", file=sys.stderr)
    return 2


def main() -> int:
    try:
        import control_plane_kit_server_sdk
    except Exception:
        return _reject()

    if not (
        "jwt" not in sys.modules
        and "cryptography" not in sys.modules
    ):
        return _reject()

    try:
        accepted = (
            version("PyJWT") == "2.13.0"
            and version("cryptography") == "50.0.0"
        )
    except PackageNotFoundError:
        return _reject()
    if not accepted:
        return _reject()

    try:
        import jwt
        import cryptography
    except Exception:
        return _reject()

    print("verification dependencies import ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
