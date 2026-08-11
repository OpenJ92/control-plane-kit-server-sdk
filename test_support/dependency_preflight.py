from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tomllib


ACCEPTED_CORE_SHA = "0ee72c3fcdfbee5094357152bdf070fbfc53393c"
ACCEPTED_DEPENDENCY = (
    "control-plane-kit-core @ "
    "https://github.com/OpenJ92/control-plane-kit/archive/"
    f"{ACCEPTED_CORE_SHA}.zip#subdirectory=control-plane-kit-core"
)
ACCEPTED_VERIFICATION_DEPENDENCIES = [
    "PyJWT==2.13.0",
    "cryptography==50.0.0",
]
ACCEPTED_FASTAPI_DEPENDENCIES = [
    *ACCEPTED_VERIFICATION_DEPENDENCIES,
    "fastapi==0.141.1",
]
ACCEPTED_OPTIONAL_DEPENDENCIES = {
    "verification": ACCEPTED_VERIFICATION_DEPENDENCIES,
    "fastapi": ACCEPTED_FASTAPI_DEPENDENCIES,
}


class DependencyPreflightError(ValueError):
    pass


def validate_dependencies(pyproject_path: Path) -> None:
    try:
        document = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise DependencyPreflightError from error

    project = document.get("project")
    dependencies = project.get("dependencies") if isinstance(project, dict) else None
    optional_dependencies = (
        project.get("optional-dependencies") if isinstance(project, dict) else None
    )
    if (
        dependencies != [ACCEPTED_DEPENDENCY]
        or optional_dependencies != ACCEPTED_OPTIONAL_DEPENDENCIES
    ):
        raise DependencyPreflightError


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pyproject", type=Path)
    arguments = parser.parse_args()

    try:
        validate_dependencies(arguments.pyproject)
    except DependencyPreflightError:
        print(
            "dependency preflight failed: dependency metadata is not accepted",
            file=sys.stderr,
        )
        return 2

    print(
        "dependency-preflight=accepted "
        "repository=OpenJ92/control-plane-kit "
        f"sha={ACCEPTED_CORE_SHA} "
        "subdirectory=control-plane-kit-core "
        "verification=PyJWT==2.13.0,cryptography==50.0.0"
        " fastapi=PyJWT==2.13.0,cryptography==50.0.0,fastapi==0.141.1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
