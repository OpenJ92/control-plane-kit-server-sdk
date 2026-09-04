from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys
import tomllib
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPOSITORY_ROOT / "pyproject.toml"
SOURCE_ROOT = REPOSITORY_ROOT / "src"
PACKAGE_ROOT = SOURCE_ROOT / "control_plane_kit_server_sdk"
CORE_DEPENDENCY = (
    "control-plane-kit-core @ "
    "https://github.com/OpenJ92/control-plane-kit/archive/"
    "0ee72c3fcdfbee5094357152bdf070fbfc53393c.zip"
    "#subdirectory=control-plane-kit-core"
)
VERIFICATION_DEPENDENCIES = [
    "PyJWT==2.13.0",
    "cryptography==50.0.0",
]
FASTAPI_DEPENDENCIES = [
    *VERIFICATION_DEPENDENCIES,
    "fastapi==0.141.1",
    "starlette==1.6.0",
]


class PackageFoundationTests(unittest.TestCase):
    def test_metadata_declares_exact_distribution_and_core_pin(self) -> None:
        self.assertTrue(PYPROJECT.is_file(), "missing package metadata: pyproject.toml")
        metadata = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

        self.assertEqual(
            metadata["build-system"],
            {
                "requires": ["setuptools>=68"],
                "build-backend": "setuptools.build_meta",
            },
        )
        project = metadata["project"]
        self.assertEqual(project["name"], "control-plane-kit-server-sdk")
        self.assertEqual(project["version"], "0.1.0")
        self.assertEqual(project["requires-python"], ">=3.11")
        self.assertEqual(project["dependencies"], [CORE_DEPENDENCY])
        self.assertEqual(
            project["optional-dependencies"],
            {
                "verification": VERIFICATION_DEPENDENCIES,
                "fastapi": FASTAPI_DEPENDENCIES,
            },
        )
        self.assertNotIn("scripts", project)
        self.assertEqual(
            metadata["tool"]["setuptools"]["packages"]["find"],
            {
                "where": ["src"],
                "include": ["control_plane_kit_server_sdk*"],
            },
        )
        setuptools = metadata["tool"]["setuptools"]
        self.assertIn("package-data", setuptools)
        self.assertEqual(
            setuptools["package-data"],
            {"control_plane_kit_server_sdk": ["py.typed"]},
        )

    def test_root_import_exports_context_without_outer_dependencies(self) -> None:
        self.assertTrue(
            (PACKAGE_ROOT / "__init__.py").is_file(),
            "missing import package: control_plane_kit_server_sdk",
        )
        script = """
import sys
import control_plane_kit_server_sdk as sdk

assert sdk.__version__ == "0.1.0"
assert sdk.__all__ == [
    "AtomicControlPlaneVariable",
    "AtomicWorkloadNodeControlSurfaceReadVerifierKeySet",
    "AtomicWorkloadNodeControlVerifierKeySet",
    "ControlPlaneInvocationContext",
    "ControlPlaneVariable",
    "WorkloadNodeControlSurfaceReadVerifierKeySet",
    "WorkloadNodeControlVerifierKeySet",
    "__version__",
]
assert sdk.AtomicControlPlaneVariable.__module__ == "control_plane_kit_server_sdk.atomic"
assert sdk.AtomicWorkloadNodeControlSurfaceReadVerifierKeySet.__module__ == "control_plane_kit_server_sdk.verifier_keys"
assert sdk.AtomicWorkloadNodeControlVerifierKeySet.__module__ == "control_plane_kit_server_sdk.verifier_keys"
assert sdk.ControlPlaneInvocationContext.__module__ == "control_plane_kit_server_sdk.context"
assert sdk.ControlPlaneVariable.__module__ == "control_plane_kit_server_sdk.protocol"
assert sdk.WorkloadNodeControlSurfaceReadVerifierKeySet.__module__ == "control_plane_kit_server_sdk.verifier_keys"
assert sdk.WorkloadNodeControlVerifierKeySet.__module__ == "control_plane_kit_server_sdk.verifier_keys"
assert "control_plane_kit_core" in sys.modules
for name in (
    "control_plane_kit_operations",
    "control_plane_kit_interpreters",
    "control_plane_kit_secrets",
    "control_plane_kit_servers",
    "fastapi",
    "starlette",
    "anyio",
    "psycopg",
    "docker",
    "cloudflare",
    "cryptography",
    "jwt",
):
    assert name not in sys.modules, name
"""
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(SOURCE_ROOT)
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_source_imports_exclude_outer_packages_and_runtime_tools(self) -> None:
        self.assertTrue(PACKAGE_ROOT.is_dir(), "missing SDK source package")
        forbidden = {
            "cloudflare",
            "control_plane_kit_operations",
            "control_plane_kit_interpreters",
            "control_plane_kit_secrets",
            "control_plane_kit_servers",
            "cryptography",
            "docker",
            "fastapi",
            "starlette",
            "anyio",
            "jwt",
            "psycopg",
        }
        findings: list[str] = []
        for path in sorted(PACKAGE_ROOT.rglob("*.py")):
            permitted: set[str] = set()
            if path.name == "verification.py":
                permitted.add("jwt")
            if path.name in {
                "_fastapi_variable_routes.py",
                "_fastapi_surface_routes.py",
                "fastapi.py",
            }:
                permitted.update({"fastapi", "starlette"})
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".", 1)[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    roots = {node.module.split(".", 1)[0]}
                else:
                    roots = set()
                for name in sorted(roots & (forbidden - permitted)):
                    findings.append(f"{path.relative_to(REPOSITORY_ROOT)} imports {name}")

        self.assertEqual(findings, [])

    def test_readme_and_decision_describe_install_and_deferred_behavior(self) -> None:
        readme = self._read("README.md")
        decision = self._read("docs/decisions/0003-distribution-foundation.md")

        for required in (
            "pip install .",
            "control_plane_kit_server_sdk",
            "__version__",
            "0ee72c3fcdfbee5094357152bdf070fbfc53393c",
            "not published",
        ):
            with self.subTest(required=required):
                self.assertIn(required, readme)
        for required in (
            "Status: Accepted",
            "#1485",
            "#1480",
            "No runtime",
            "No package publication",
        ):
            with self.subTest(required=required):
                self.assertIn(required, decision)

    def test_verification_extra_docs_define_dependency_only_boundary(self) -> None:
        readme = self._read("README.md")
        decision = self._read(
            "docs/decisions/0009-verification-dependency-proof.md"
        )

        for document in (readme, decision):
            for required in (
                ".[verification]",
                "PyJWT==2.13.0",
                "cryptography==50.0.0",
                "#1498",
            ):
                with self.subTest(document=document[:24], required=required):
                    self.assertIn(required, document)
        self.assertIn("dependency availability", decision)
        self.assertIn("No verifier behavior", decision)
        for document in (readme, decision):
            for required in (
                "named direct dependencies",
                "do not lock transitive dependency versions",
                "artifact hashes",
                "publisher attestations",
            ):
                with self.subTest(document=document[:24], required=required):
                    self.assertIn(required, document)
        self.assertNotIn("reproducible dependency pair", decision)

    def _read(self, relative_path: str) -> str:
        path = REPOSITORY_ROOT / relative_path
        self.assertTrue(path.is_file(), f"missing package artifact: {relative_path}")
        return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
