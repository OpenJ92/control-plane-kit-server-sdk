from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest


VALID_TEST = """\
import unittest

class ExampleTests(unittest.TestCase):
    def test_value(self):
        self.assertEqual(1 + 1, 2)
"""


class PackageIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.package_root = Path(
            os.environ.get("CPK_PACKAGE_ROOT", Path(__file__).resolve().parents[2])
        )

    def _load_module(self) -> types.ModuleType:
        path = self.package_root / "test_support" / "package_integrity.py"
        self.assertTrue(path.is_file(), "missing package-integrity implementation")
        spec = importlib.util.spec_from_file_location("package_integrity", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def _inspect(
        self,
        *,
        test_document: str = VALID_TEST,
        test_name: str = "test_example.py",
        source_document: str = "",
        gate_document: str = "python -m unittest\n",
        approvals: object = (),
    ):
        module = self._load_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "src"
            tests = root / "tests"
            source.mkdir()
            tests.mkdir()
            if source_document:
                (source / "module.py").write_text(source_document, encoding="utf-8")
            (tests / test_name).write_text(test_document, encoding="utf-8")
            approvals_path = tests / "approved_skips.json"
            approvals_path.write_text(json.dumps(approvals), encoding="utf-8")
            gate = root / "test.sh"
            gate.write_text(gate_document, encoding="utf-8")
            return module.inspect_package(
                root,
                source_roots=(source,),
                test_roots=(tests,),
                gate_files=(gate,),
                approved_skips_path=approvals_path,
            )

    def assert_code(self, report, code: str) -> None:
        self.assertIn(code, {finding.code for finding in report.findings})

    def test_valid_unittest_package_reports_exact_identity(self) -> None:
        report = self._inspect()

        self.assertTrue(report.valid)
        self.assertEqual(
            report.test_identities,
            ("tests/test_example.py::ExampleTests.test_value",),
        )

    def test_collection_and_source_negative_matrix_fails_closed(self) -> None:
        nested = (
            "import unittest\n"
            "def factory():\n"
            "    class NestedTests(unittest.TestCase):\n"
            "        def test_hidden(self):\n"
            "            self.assertTrue(True)\n"
            "    return NestedTests\n"
        )
        swallowed = VALID_TEST.replace(
            "self.assertEqual(1 + 1, 2)",
            "try:\n            raise ValueError('failure')\n"
            "        except ValueError:\n            pass",
        )
        cases = (
            ("hidden-test-file", {"test_name": "hidden.py"}),
            ("hidden-test-function", {"test_document": "def test_hidden():\n    assert True\n"}),
            ("hidden-test-class", {"test_document": nested}),
            (
                "placeholder-test",
                {"test_document": VALID_TEST.replace("self.assertEqual(1 + 1, 2)", "pass")},
            ),
            ("swallowed-exception", {"test_document": swallowed}),
            ("mutable-legacy-import", {"source_document": "import control_plane_kit\n"}),
            ("pytest-import", {"test_document": "import pytest\n" + VALID_TEST}),
            (
                "proof-changing-option",
                {"gate_document": 'if [ "${CPK_SKIP_TESTS:-0}" = 1 ]; then exit 0; fi\n'},
            ),
        )
        for expected, values in cases:
            with self.subTest(expected=expected):
                self.assert_code(self._inspect(**values), expected)

    def test_skip_approval_matrix_fails_closed(self) -> None:
        identity = "tests/test_example.py::ExampleTests.test_value"
        conditional = VALID_TEST.replace(
            "    def test_value",
            '    @unittest.skipIf(condition(), "bounded reason")\n    def test_value',
        )
        literal = VALID_TEST.replace(
            "    def test_value",
            '    @unittest.skipIf(False, "bounded reason")\n    def test_value',
        )
        unconditional = VALID_TEST.replace(
            "    def test_value",
            '    @unittest.skip("later")\n    def test_value',
        )
        cases = (
            ("unconditional-skip", {"test_document": unconditional}),
            ("literal-skip-condition", {"test_document": literal}),
            ("unapproved-skip", {"test_document": conditional}),
            (
                "duplicate-skip-approval",
                {
                    "approvals": [
                        {"identity": identity, "reason": "bounded reason"},
                        {"identity": identity, "reason": "bounded reason"},
                    ]
                },
            ),
            ("invalid-skip-approval", {"approvals": [{"identity": identity, "reason": ""}]}),
            ("stale-skip-approval", {"approvals": [{"identity": "missing", "reason": "bounded"}]}),
        )
        for expected, values in cases:
            with self.subTest(expected=expected):
                self.assert_code(self._inspect(**values), expected)

        approved = self._inspect(
            test_document=conditional,
            approvals=[{"identity": identity, "reason": "bounded reason"}],
        )
        self.assertTrue(approved.valid)
        self.assertEqual(approved.approved_skip_identities, (identity,))

    def test_mocks_are_bounded_evidence_not_integrity_failures(self) -> None:
        report = self._inspect(test_document="from unittest.mock import patch\n" + VALID_TEST)

        self.assertTrue(report.valid)
        self.assertEqual(report.mock_locations, ("tests/test_example.py:1",))


if __name__ == "__main__":
    unittest.main()
