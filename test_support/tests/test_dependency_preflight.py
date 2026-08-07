from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ACCEPTED_DEPENDENCY = (
    "control-plane-kit-core @ "
    "https://github.com/OpenJ92/control-plane-kit/archive/"
    "3d85dc76300bf88be923531445ce83e9b6c7b23e.zip"
    "#subdirectory=control-plane-kit-core"
)


class DependencyPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(
            os.environ.get("CPK_PACKAGE_ROOT", Path(__file__).resolve().parents[2])
        )
        cls.preflight = cls.root / "test_support" / "dependency_preflight.py"
        cls.pyproject = cls.root / "pyproject.toml"
        cls.gate = cls.root / "test.sh"

    def _run_preflight(self, document: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            pyproject = Path(temporary_directory) / "pyproject.toml"
            pyproject.write_text(document, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(self.preflight), str(pyproject)],
                check=False,
                capture_output=True,
                text=True,
            )

    def _mutations(self) -> tuple[tuple[str, str], ...]:
        accepted = self.pyproject.read_text(encoding="utf-8")
        return (
            (
                "mutable-ref",
                accepted.replace(
                    "3d85dc76300bf88be923531445ce83e9b6c7b23e.zip",
                    "main.zip",
                ),
            ),
            (
                "wrong-repository",
                accepted.replace(
                    "OpenJ92/control-plane-kit/archive",
                    "OpenJ92/another-package/archive",
                ),
            ),
            (
                "wrong-full-sha",
                accepted.replace(
                    "3d85dc76300bf88be923531445ce83e9b6c7b23e",
                    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                ),
            ),
            (
                "missing-subdirectory",
                accepted.replace("#subdirectory=control-plane-kit-core", ""),
            ),
            (
                "extra-dependency",
                accepted.replace(
                    f'  "{ACCEPTED_DEPENDENCY}",',
                    f'  "{ACCEPTED_DEPENDENCY}",\n  "another-package==1",',
                ),
            ),
        )

    def test_exact_accepted_dependency_is_admitted(self) -> None:
        completed = self._run_preflight(self.pyproject.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("dependency-preflight=accepted", completed.stdout)
        self.assertIn("3d85dc76300bf88be923531445ce83e9b6c7b23e", completed.stdout)

    def test_mutable_or_wrong_coordinates_are_rejected_by_structured_preflight(self) -> None:
        for identity, document in self._mutations():
            with self.subTest(identity=identity):
                completed = self._run_preflight(document)
                self.assertEqual(completed.returncode, 2)
                self.assertIn("dependency preflight failed", completed.stderr)
                self.assertNotIn("phase=package-build", completed.stdout)
                self.assertNotIn("pip install", completed.stdout)

    def test_gate_rejects_drift_before_build_or_dependency_install(self) -> None:
        for identity, document in self._mutations():
            with self.subTest(identity=identity):
                completed, events = self._run_gate_with_fake_docker(document)
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn("dependency preflight failed", completed.stderr)
                self.assertNotIn("phase=package-build", completed.stdout)
                self.assertNotIn("phase=package-build", events)
                self.assertNotIn("dependency-resolving-pip", events)

    def _run_gate_with_fake_docker(
        self,
        document: str,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            binary = root / "bin"
            binary.mkdir()
            gate = root / "test.sh"
            shutil.copy2(self.gate, gate)
            pyproject = root / "pyproject.toml"
            pyproject.write_text(document, encoding="utf-8")
            events = root / "events.log"
            fake_docker = binary / "docker"
            fake_docker.write_text(
                """#!/usr/bin/env python3
from pathlib import Path
import os
import subprocess
import sys

arguments = sys.argv[1:]
joined = " ".join(arguments)
events = Path(os.environ["CPK_PREFLIGHT_EVENTS"])

if arguments[:1] == ["build"]:
    events.write_text(events.read_text() + "phase=package-build\\n")
    raise SystemExit(0)
if "dependency_preflight.py" in joined:
    completed = subprocess.run(
        [
            sys.executable,
            os.environ["CPK_PREFLIGHT_SCRIPT"],
            os.environ["CPK_PREFLIGHT_PYPROJECT"],
        ],
        check=False,
    )
    raise SystemExit(completed.returncode)
if arguments[:1] == ["run"] and "phase=package-build" in events.read_text():
    events.write_text(events.read_text() + "dependency-resolving-pip\\n")
raise SystemExit(0)
""",
                encoding="utf-8",
            )
            fake_docker.chmod(0o755)
            events.write_text("", encoding="utf-8")
            environment = dict(os.environ)
            environment.update(
                {
                    "PATH": f"{binary}:{environment['PATH']}",
                    "CPK_PREFLIGHT_EVENTS": str(events),
                    "CPK_PREFLIGHT_SCRIPT": str(self.preflight),
                    "CPK_PREFLIGHT_PYPROJECT": str(pyproject),
                }
            )
            completed = subprocess.run(
                [str(gate)],
                cwd=root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            return completed, events.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
