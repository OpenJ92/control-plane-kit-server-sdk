from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
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

    def test_optional_local_core_mount_is_bash_32_nounset_safe(self) -> None:
        source = self._read("test.sh")
        portable_expansion = '${CORE_MOUNT_ARGS[@]+"${CORE_MOUNT_ARGS[@]}"}'
        mount_lines = [
            line.strip().removesuffix(" \\")
            for line in source.splitlines()
            if "CORE_MOUNT_ARGS[@]" in line
        ]

        self.assertEqual(mount_lines, [portable_expansion] * 3)
        script = (
            "set -u; "
            "CORE_MOUNT_ARGS=(); "
            f"set -- {portable_expansion}; test \"$#\" -eq 0; "
            "CORE_MOUNT_ARGS=(-v '/path with space:/workspace:ro'); "
            f"set -- {portable_expansion}; "
            "test \"$#\" -eq 2; test \"$1\" = -v; "
            "test \"$2\" = '/path with space:/workspace:ro'"
        )
        completed = subprocess.run(
            ["/bin/bash", "-c", script],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

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
            "python /test-support/dependency_preflight.py",
            "docker build --target test",
            "phase=base-install",
            "python /test-support/installed_import.py",
            "phase=verification-extra-install",
            ".[verification]",
            "python /test-support/installed_verification_dependencies.py",
            "phase=fastapi-extra-install",
            ".[fastapi]",
            "python -m compileall src tests",
            "python -m unittest discover -s tests -v",
            "python /test-support/installed_fastapi_dependencies.py",
        )
        offsets: list[int] = []
        start = 0
        for phase in phases:
            offset = source.find(phase, start)
            self.assertGreaterEqual(offset, 0, phase)
            offsets.append(offset)
            start = offset + len(phase)
        self.assertEqual(offsets, sorted(offsets))
        base_phase = source[
            source.index("phase=base-install")
            : source.index("phase=verification-extra-install")
        ]
        verification_phase = source[
            source.index("phase=verification-extra-install") :
        ]
        self.assertNotIn("python -m compileall src tests", base_phase)
        self.assertNotIn("python -m unittest discover -s tests -v", base_phase)
        self.assertEqual(
            verification_phase.count("python -m compileall src tests"),
            1,
        )
        self.assertEqual(
            verification_phase.count("python -m unittest discover -s tests -v"),
            1,
        )
        self.assertEqual(source.count("python -m compileall src tests"), 1)
        self.assertEqual(
            source.count("python -m unittest discover -s tests -v"),
            2,
        )
        self.assertIn('RUN_ID="$$"', source)
        self.assertIn(
            'BASE_CONTAINER_NAME="cpk-server-sdk-base-${RUN_ID}"', source
        )
        self.assertIn(
            'VERIFICATION_CONTAINER_NAME="cpk-server-sdk-verification-${RUN_ID}"',
            source,
        )
        self.assertIn(
            'FASTAPI_CONTAINER_NAME="cpk-server-sdk-fastapi-${RUN_ID}"',
            source,
        )
        self.assertIn('docker rm -f "$BASE_CONTAINER_NAME"', source)
        self.assertIn('docker rm -f "$VERIFICATION_CONTAINER_NAME"', source)
        self.assertIn('docker rm -f "$FASTAPI_CONTAINER_NAME"', source)
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
        self.assertIn(
            "COPY test_support/installed_verification_dependencies.py "
            "./test_support/",
            source,
        )
        self.assertIn(
            "COPY test_support/installed_fastapi_dependencies.py "
            "./test_support/",
            source,
        )
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
                "test_support/*",
                "!test_support/installed_verification_dependencies.py",
                "!test_support/installed_fastapi_dependencies.py",
            }.issubset(ignored)
        )

    def test_each_package_run_fails_fast_before_import_smoke(self) -> None:
        source = self._read("test.sh")

        self.assertEqual(source.count("sh -ceu '"), 3)

    def test_installed_import_proves_context_and_forbidden_dependencies(self) -> None:
        gate = self._read("test.sh")
        source = self._read("test_support/installed_import.py")

        self.assertEqual(gate.count("python /test-support/installed_import.py"), 3)
        for expected in (
            "control_plane_kit_server_sdk.__version__",
            "ControlPlaneInvocationContext",
            "ControlPlaneVariable",
            "unexpected installed SDK context owner",
            "unexpected installed SDK protocol owner",
            "installed SDK type marker is missing or malformed",
            "control_plane_kit_core",
            "control_plane_kit_operations",
            "fastapi",
            "unexpected forbidden import",
            "installed context did not load the pinned core contract",
            "control-plane-kit-server-sdk import ok",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)

    def test_installed_verification_probe_is_exact_and_root_lazy(self) -> None:
        gate = self._read("test.sh")
        source = self._read(
            "test_support/installed_verification_dependencies.py"
        )

        self.assertIn(
            "python /test-support/installed_verification_dependencies.py",
            gate,
        )
        for expected in (
            'version("PyJWT")',
            'version("cryptography")',
            '"2.13.0"',
            '"50.0.0"',
            "import control_plane_kit_server_sdk",
            '"jwt" not in sys.modules',
            '"cryptography" not in sys.modules',
            "import jwt",
            "import cryptography",
            "verification dependencies import ok",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)

    def test_installed_fastapi_probe_is_exact_and_root_lazy(self) -> None:
        gate = self._read("test.sh")
        source = self._read("test_support/installed_fastapi_dependencies.py")

        self.assertIn(
            "python /test-support/installed_fastapi_dependencies.py",
            gate,
        )
        self.assertIn(
            'python -m pip install "PyJWT==2.13.0" "cryptography==50.0.0" '
            '"fastapi==0.141.1" "starlette==1.6.0"',
            gate,
        )
        for expected in (
            'version("PyJWT")',
            'version("cryptography")',
            'version("fastapi")',
            'version("starlette")',
            '"2.13.0"',
            '"50.0.0"',
            '"0.141.1"',
            '"1.6.0"',
            "import control_plane_kit_server_sdk",
            '"fastapi" not in sys.modules',
            '"starlette" not in sys.modules',
            '"anyio" not in sys.modules',
            '"jwt" not in sys.modules',
            '"cryptography" not in sys.modules',
            "import control_plane_kit_server_sdk.fastapi as sdk_fastapi",
            "fastapi dependencies import ok",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)

    def test_installed_fastapi_probe_executes_exact_version_contract(self) -> None:
        cases = (
            ("accepted", "2.13.0", "50.0.0", "0.141.1", "1.6.0", True),
            ("wrong-pyjwt", "2.12.0", "50.0.0", "0.141.1", "1.6.0", False),
            ("wrong-cryptography", "2.13.0", "49.0.0", "0.141.1", "1.6.0", False),
            ("wrong-fastapi", "2.13.0", "50.0.0", "0.140.0", "1.6.0", False),
            ("wrong-starlette", "2.13.0", "50.0.0", "0.141.1", "1.5.0", False),
        )
        for (
            identity,
            pyjwt_version,
            cryptography_version,
            fastapi_version,
            starlette_version,
            accepted,
        ) in cases:
            with self.subTest(identity=identity):
                completed, events, temporary_root = self._run_fastapi_probe(
                    pyjwt_version=pyjwt_version,
                    cryptography_version=cryptography_version,
                    fastapi_version=fastapi_version,
                    starlette_version=starlette_version,
                )
                if accepted:
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(
                        completed.stdout,
                        "fastapi dependencies import ok\n",
                    )
                    self.assertEqual(completed.stderr, "")
                    self.assertEqual(
                        events,
                        "sdk\nfastapi\nstarlette\nanyio\njwt\ncryptography\nadapter\n",
                    )
                else:
                    self.assertEqual(completed.returncode, 2)
                    self.assertEqual(completed.stdout, "")
                    self.assertEqual(
                        completed.stderr,
                        "fastapi dependencies are not accepted\n",
                    )
                    self.assertLessEqual(len(completed.stderr.encode("utf-8")), 128)
                    self.assertEqual(events, "sdk\n")
                    for excluded in (
                        pyjwt_version,
                        cryptography_version,
                        fastapi_version,
                        starlette_version,
                        str(temporary_root),
                        "sensitive fake module material",
                    ):
                        with self.subTest(identity=identity, excluded=excluded):
                            self.assertNotIn(
                                excluded,
                                completed.stdout + completed.stderr,
                            )

    def test_installed_fastapi_probe_bounds_metadata_backend_failure(self) -> None:
        probe = self.root / "test_support" / "installed_fastapi_dependencies.py"
        completed, events, temporary_root = self._run_fastapi_environment(
            pyjwt_version="2.13.0",
            cryptography_version="50.0.0",
            fastapi_version="0.141.1",
            starlette_version="1.6.0",
            arguments=(
                sys.executable,
                "-c",
                "import importlib.metadata\n"
                "import runpy\n"
                "def fail_version(_name):\n"
                "    raise RuntimeError('sensitive metadata backend failure')\n"
                "importlib.metadata.version = fail_version\n"
                f"runpy.run_path({str(probe)!r}, run_name='__main__')\n",
            ),
        )

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(
            completed.stderr,
            "fastapi dependencies are not accepted\n",
        )
        self.assertLessEqual(len(completed.stderr.encode("utf-8")), 128)
        self.assertEqual(events, "sdk\n")
        for excluded in (
            "sensitive metadata backend failure",
            "RuntimeError",
            "Traceback",
            str(temporary_root),
        ):
            with self.subTest(excluded=excluded):
                self.assertNotIn(excluded, completed.stdout + completed.stderr)

    def test_installed_verification_probe_executes_exact_version_contract(self) -> None:
        cases = (
            ("accepted", "2.13.0", "50.0.0", True),
            ("wrong-pyjwt", "2.12.0", "50.0.0", False),
            ("wrong-cryptography", "2.13.0", "49.0.0", False),
        )
        for identity, pyjwt_version, cryptography_version, accepted in cases:
            with self.subTest(identity=identity):
                completed, events, temporary_root = self._run_verification_probe(
                    pyjwt_version=pyjwt_version,
                    cryptography_version=cryptography_version,
                )
                if accepted:
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(
                        completed.stdout,
                        "verification dependencies import ok\n",
                    )
                    self.assertEqual(completed.stderr, "")
                    self.assertEqual(events, "sdk\njwt\ncryptography\n")
                else:
                    self.assertEqual(completed.returncode, 2)
                    self.assertEqual(completed.stdout, "")
                    self.assertEqual(
                        completed.stderr,
                        "verification dependencies are not accepted\n",
                    )
                    self.assertLessEqual(len(completed.stderr.encode("utf-8")), 128)
                    self.assertEqual(events, "sdk\n")
                    for excluded in (
                        pyjwt_version,
                        cryptography_version,
                        str(temporary_root),
                        "sensitive fake module material",
                    ):
                        with self.subTest(identity=identity, excluded=excluded):
                            self.assertNotIn(
                                excluded,
                                completed.stdout + completed.stderr,
                            )

    def test_verification_probe_fixture_is_resolver_free_and_executable(self) -> None:
        completed, events, _temporary_root = self._run_verification_environment(
            pyjwt_version="2.13.0",
            cryptography_version="50.0.0",
            arguments=(
                sys.executable,
                "-c",
                "from importlib.metadata import version; "
                "import control_plane_kit_server_sdk; "
                "assert version('PyJWT') == '2.13.0'; "
                "assert version('cryptography') == '50.0.0'; "
                "import jwt; import cryptography; print('fixture ok')",
            ),
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, "fixture ok\n")
        self.assertEqual(completed.stderr, "")
        self.assertEqual(events, "sdk\njwt\ncryptography\n")

    def test_installed_verification_probe_bounds_metadata_backend_failure(self) -> None:
        probe = (
            self.root / "test_support" / "installed_verification_dependencies.py"
        )
        completed, events, temporary_root = self._run_verification_environment(
            pyjwt_version="2.13.0",
            cryptography_version="50.0.0",
            arguments=(
                sys.executable,
                "-c",
                "import importlib.metadata\n"
                "import runpy\n"
                "def fail_version(_name):\n"
                "    raise RuntimeError('sensitive metadata backend failure')\n"
                "importlib.metadata.version = fail_version\n"
                f"runpy.run_path({str(probe)!r}, run_name='__main__')\n",
            ),
        )

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(
            completed.stderr,
            "verification dependencies are not accepted\n",
        )
        self.assertLessEqual(len(completed.stderr.encode("utf-8")), 128)
        self.assertEqual(events, "sdk\n")
        for excluded in (
            "sensitive metadata backend failure",
            "RuntimeError",
            "Traceback",
            str(temporary_root),
        ):
            with self.subTest(excluded=excluded):
                self.assertNotIn(excluded, completed.stdout + completed.stderr)

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

    def _run_verification_probe(
        self,
        *,
        pyjwt_version: str,
        cryptography_version: str,
    ) -> tuple[subprocess.CompletedProcess[str], str, Path]:
        return self._run_verification_environment(
            pyjwt_version=pyjwt_version,
            cryptography_version=cryptography_version,
            arguments=(
                sys.executable,
                str(
                    self.root
                    / "test_support"
                    / "installed_verification_dependencies.py"
                ),
            ),
        )

    def _run_fastapi_probe(
        self,
        *,
        pyjwt_version: str,
        cryptography_version: str,
        fastapi_version: str,
        starlette_version: str,
    ) -> tuple[subprocess.CompletedProcess[str], str, Path]:
        return self._run_fastapi_environment(
            pyjwt_version=pyjwt_version,
            cryptography_version=cryptography_version,
            fastapi_version=fastapi_version,
            starlette_version=starlette_version,
            arguments=(
                sys.executable,
                str(
                    self.root
                    / "test_support"
                    / "installed_fastapi_dependencies.py"
                ),
            ),
        )

    def _run_fastapi_environment(
        self,
        *,
        pyjwt_version: str,
        cryptography_version: str,
        fastapi_version: str,
        starlette_version: str,
        arguments: tuple[str, ...],
    ) -> tuple[subprocess.CompletedProcess[str], str, Path]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            events = root / "events.log"
            events.write_text("", encoding="utf-8")
            self._write_fake_module(
                root,
                "control_plane_kit_server_sdk",
                """
import os
from pathlib import Path
import sys

for name in ("fastapi", "starlette", "anyio", "jwt", "cryptography"):
    if name in sys.modules:
        raise RuntimeError("optional dependency loaded before SDK root")
with Path(os.environ["CPK_FASTAPI_PROBE_EVENTS"]).open("a") as stream:
    stream.write("sdk\\n")
""",
            )
            (
                root
                / "control_plane_kit_server_sdk"
                / "fastapi.py"
            ).write_text(
                "import fastapi\n"
                "import jwt\n"
                "import cryptography\n"
                "import os\n"
                "from pathlib import Path\n"
                "with Path(os.environ['CPK_FASTAPI_PROBE_EVENTS']).open('a') as stream:\n"
                "    stream.write('adapter\\n')\n"
                "def install_cpk_control_routes():\n"
                "    return None\n"
                "__all__ = ['install_cpk_control_routes']\n",
                encoding="utf-8",
            )
            self._write_fake_module(
                root,
                "fastapi",
                """
import os
from pathlib import Path
import sys

if "control_plane_kit_server_sdk" not in sys.modules:
    raise RuntimeError("SDK root was not imported first")
with Path(os.environ["CPK_FASTAPI_PROBE_EVENTS"]).open("a") as stream:
    stream.write("fastapi\\n")
import starlette
import anyio
""",
            )
            for name in ("starlette", "anyio", "jwt", "cryptography"):
                self._write_fake_module(
                    root,
                    name,
                    f"""
import os
from pathlib import Path
with Path(os.environ["CPK_FASTAPI_PROBE_EVENTS"]).open("a") as stream:
    stream.write("{name}\\n")
SENSITIVE = "sensitive fake module material"
""",
                )
            self._write_fake_distribution(root, "PyJWT", pyjwt_version)
            self._write_fake_distribution(
                root,
                "cryptography",
                cryptography_version,
            )
            self._write_fake_distribution(root, "fastapi", fastapi_version)
            self._write_fake_distribution(root, "starlette", starlette_version)
            environment = dict(os.environ)
            environment.update(
                {
                    "CPK_FASTAPI_PROBE_EVENTS": str(events),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(root),
                }
            )
            completed = subprocess.run(
                arguments,
                cwd=root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            return completed, events.read_text(encoding="utf-8"), root

    def _run_verification_environment(
        self,
        *,
        pyjwt_version: str,
        cryptography_version: str,
        arguments: tuple[str, ...],
    ) -> tuple[subprocess.CompletedProcess[str], str, Path]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            events = root / "events.log"
            events.write_text("", encoding="utf-8")
            self._write_fake_module(
                root,
                "control_plane_kit_server_sdk",
                """
import os
from pathlib import Path
import sys

if "jwt" in sys.modules or "cryptography" in sys.modules:
    raise RuntimeError("optional dependency loaded before SDK root")
with Path(os.environ["CPK_VERIFICATION_PROBE_EVENTS"]).open("a") as stream:
    stream.write("sdk\\n")
""",
            )
            (root / "control_plane_kit_server_sdk" / "verification.py").write_text(
                "import jwt\n"
                "class Ed25519WorkloadNodeControlSurfaceReadVerifier:\n"
                "    pass\n"
                "class Ed25519WorkloadNodeControlVerifier:\n"
                "    pass\n\n"
                "class Ed25519WorkloadNodeHealthReadVerifier:\n"
                "    pass\n",
                encoding="utf-8",
            )
            (root / "control_plane_kit_server_sdk" / "health.py").write_text(
                "class WorkloadNodeHealthReadDispatcher:\n    pass\n",
                encoding="utf-8",
            )
            self._write_fake_module(
                root,
                "jwt",
                """
import os
from pathlib import Path
import sys

if "control_plane_kit_server_sdk" not in sys.modules:
    raise RuntimeError("SDK root was not imported first")
with Path(os.environ["CPK_VERIFICATION_PROBE_EVENTS"]).open("a") as stream:
    stream.write("jwt\\n")
SENSITIVE = "sensitive fake module material"
""",
            )
            self._write_fake_module(
                root,
                "cryptography",
                """
import os
from pathlib import Path
import sys

if "control_plane_kit_server_sdk" not in sys.modules:
    raise RuntimeError("SDK root was not imported first")
with Path(os.environ["CPK_VERIFICATION_PROBE_EVENTS"]).open("a") as stream:
    stream.write("cryptography\\n")
SENSITIVE = "sensitive fake module material"
""",
            )
            self._write_fake_distribution(root, "PyJWT", pyjwt_version)
            self._write_fake_distribution(
                root,
                "cryptography",
                cryptography_version,
            )
            environment = dict(os.environ)
            environment.update(
                {
                    "CPK_VERIFICATION_PROBE_EVENTS": str(events),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(root),
                }
            )
            completed = subprocess.run(
                arguments,
                cwd=root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            return completed, events.read_text(encoding="utf-8"), root

    @staticmethod
    def _write_fake_module(root: Path, name: str, source: str) -> None:
        package = root / name
        package.mkdir()
        (package / "__init__.py").write_text(source.lstrip(), encoding="utf-8")

    @staticmethod
    def _write_fake_distribution(root: Path, name: str, version: str) -> None:
        metadata = root / f"{name}-{version}.dist-info"
        metadata.mkdir()
        (metadata / "METADATA").write_text(
            "Metadata-Version: 2.1\n"
            f"Name: {name}\n"
            f"Version: {version}\n",
            encoding="utf-8",
        )

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
