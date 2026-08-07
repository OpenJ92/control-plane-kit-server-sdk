from __future__ import annotations

import os
from pathlib import Path
import unittest


class PackageGateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(
            os.environ.get("CPK_PACKAGE_ROOT", Path(__file__).resolve().parents[2])
        )

    def _read(self, relative_path: str) -> str:
        path = self.root / relative_path
        self.assertTrue(path.is_file(), f"missing gate artifact: {relative_path}")
        return path.read_text(encoding="utf-8")

    def test_gate_is_executable_and_anchors_itself_to_repository_root(self) -> None:
        gate = self.root / "test.sh"
        source = self._read("test.sh")

        self.assertTrue(os.access(gate, os.X_OK))
        self.assertIn('ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"', source)
        self.assertIn('cd "$ROOT"', source)

    def test_dependency_modes_are_closed_and_explicit(self) -> None:
        source = self._read("test.sh")

        self.assertIn(
            'DEPENDENCY_MODE="${CPK_SERVER_SDK_DEPENDENCY_MODE:-pinned}"', source
        )
        self.assertIn('CORE_REPO="${CPK_CORE_REPO:-}"', source)
        self.assertIn("pinned)", source)
        self.assertIn("local-core)", source)
        self.assertIn("unsupported CPK_SERVER_SDK_DEPENDENCY_MODE", source)
        self.assertIn(
            "local-core mode requires CPK_CORE_REPO containing control-plane-kit-core",
            source,
        )
        self.assertIn(
            "CPK_CORE_REPO requires CPK_SERVER_SDK_DEPENDENCY_MODE=local-core",
            source,
        )
        self.assertNotIn("../control-plane-kit", source)

    def test_structured_dependency_preflight_precedes_build_and_pip(self) -> None:
        source = self._read("test.sh")

        self.assertIn("phase=dependency-preflight", source)
        self.assertIn("dependency_preflight.py", source)
        preflight = source.index("phase=dependency-preflight")
        structured_check = source.index("dependency_preflight.py")
        package_build = source.index("phase=package-build")
        dependency_pip = source.index("python -m pip install")
        self.assertLess(preflight, structured_check)
        self.assertLess(structured_check, package_build)
        self.assertLess(package_build, dependency_pip)
        self.assertNotIn("grep 'https://github.com/OpenJ92/.*/archive/'", source)

    def test_gate_orders_integrity_build_test_import_and_exact_cleanup(self) -> None:
        source = self._read("test.sh")

        phases = (
            "python -m unittest discover -s tests -v",
            "python /test-support/package_integrity.py",
            "docker build --target test",
            "python -m compileall src tests",
            "python -m unittest discover -s tests -v",
            "python /test-support/installed_import.py",
        )
        offsets: list[int] = []
        start = 0
        for phase in phases:
            offset = source.find(phase, start)
            self.assertGreaterEqual(offset, 0, phase)
            offsets.append(offset)
            start = offset + len(phase)
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn('RUN_ID="$$"', source)
        self.assertIn('docker rm -f "$CONTAINER_NAME"', source)
        self.assertIn('docker image rm -f "$IMAGE_NAME"', source)
        self.assertNotIn("docker system prune", source)
        self.assertNotIn("docker container prune", source)
        self.assertNotIn("docker image prune", source)

    def test_dockerfile_has_package_and_test_stages_without_host_python(self) -> None:
        source = self._read("Dockerfile")
        ignored = set(self._read(".dockerignore").splitlines())

        self.assertIn("ARG PYTHON_VERSION=3.14", source)
        self.assertIn("FROM python:${PYTHON_VERSION}-slim AS package", source)
        self.assertIn(
            "COPY AGENTS.md GIT-FLOW.md .gitignore pyproject.toml README.md ./",
            source,
        )
        self.assertIn("COPY docs ./docs", source)
        self.assertIn("python -m pip install --no-deps .", source)
        self.assertNotIn("pip install --upgrade pip", source)
        self.assertIn("FROM package AS test", source)
        self.assertIn("COPY tests ./tests", source)
        self.assertNotIn("pytest", source)
        self.assertTrue(
            {
                ".git",
                ".github",
                ".venv",
                "__pycache__",
                "*.py[cod]",
                "build",
                "dist",
                "*.egg-info",
                "test_support",
            }.issubset(ignored)
        )

    def test_each_package_run_fails_fast_before_import_smoke(self) -> None:
        source = self._read("test.sh")

        self.assertEqual(source.count("sh -ceu '"), 2)

    def test_installed_import_proves_context_and_forbidden_dependencies(self) -> None:
        gate = self._read("test.sh")
        source = self._read("test_support/installed_import.py")

        self.assertEqual(gate.count("python /test-support/installed_import.py"), 2)
        for expected in (
            "control_plane_kit_server_sdk.__version__",
            "ControlPlaneInvocationContext",
            "unexpected installed SDK context owner",
            "control_plane_kit_core",
            "control_plane_kit_operations",
            "fastapi",
            "unexpected forbidden import",
            "installed context did not load the pinned core contract",
            "control-plane-kit-server-sdk import ok",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)

    def test_workflow_is_read_only_and_invokes_only_the_authoritative_gate(self) -> None:
        source = self._read(".github/workflows/tests.yml")

        for expected in (
            "pull_request:",
            "workflow_dispatch:",
            "- main",
            "- develop",
            "contents: read",
            "timeout-minutes: 30",
            "cancel-in-progress: true",
            "run: ./test.sh",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)
        self.assertEqual(source.count("run: ./test.sh"), 1)
        for forbidden in (
            "packages: write",
            "id-token: write",
            "docker/login-action",
            "ghcr.io",
            "pypi",
            "twine",
            "CPK_CORE_REPO",
            "secrets.",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_decision_and_readme_define_honest_evidence_modes(self) -> None:
        decision = self._read("docs/decisions/0004-package-integrity-and-ci.md")
        readme = self._read("README.md")

        for expected in (
            "Status: Accepted",
            "pinned",
            "local-core",
            "composition evidence",
            "contents: read",
            "No package publication",
            "#1480",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, decision)
        for expected in (
            "./test.sh",
            "CPK_SERVER_SDK_DEPENDENCY_MODE=local-core",
            "CPK_CORE_REPO=",
            "not the default package or CI proof",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, readme)


if __name__ == "__main__":
    unittest.main()
