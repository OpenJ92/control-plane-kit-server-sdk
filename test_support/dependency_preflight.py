from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tomllib


ACCEPTED_CORE_SHA = "3d85dc76300bf88be923531445ce83e9b6c7b23e"
ACCEPTED_DEPENDENCY = (
    "control-plane-kit-core @ "
    "https://github.com/OpenJ92/control-plane-kit/archive/"
    f"{ACCEPTED_CORE_SHA}.zip#subdirectory=control-plane-kit-core"
)


class DependencyPreflightError(ValueError):
    pass


def validate_dependencies(pyproject_path: Path) -> None:
    try:
        document = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise DependencyPreflightError from error

    project = document.get("project")
    dependencies = project.get("dependencies") if isinstance(project, dict) else None
    if dependencies != [ACCEPTED_DEPENDENCY]:
        raise DependencyPreflightError


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pyproject", type=Path)
    arguments = parser.parse_args()

    try:
        validate_dependencies(arguments.pyproject)
    except DependencyPreflightError:
        print(
            "dependency preflight failed: project.dependencies must equal "
            "the accepted one-element core coordinate",
            file=sys.stderr,
        )
        return 2

    print(
        "dependency-preflight=accepted "
        "repository=OpenJ92/control-plane-kit "
        f"sha={ACCEPTED_CORE_SHA} "
        "subdirectory=control-plane-kit-core"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
