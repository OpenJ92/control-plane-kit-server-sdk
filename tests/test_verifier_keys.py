from __future__ import annotations

import ast
from dataclasses import fields
import importlib
import inspect
from pathlib import Path
from threading import Barrier, Thread
import textwrap
import unittest

from control_plane_kit_core import (
    DelegationKeyAlgorithm,
    DelegationKeyPurpose,
    DelegationPublicKey,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "control_plane_kit_server_sdk"
VERIFIER_KEYS_MODULE = "control_plane_kit_server_sdk.verifier_keys"


class PublicKeySubclass(DelegationPublicKey):
    pass


class SensitiveText(str):
    def __repr__(self) -> str:
        return "authorization: Bearer nested-key-secret"

    def __eq__(self, other: object) -> bool:
        raise AssertionError("nested key equality must not run")

    def __lt__(self, other: object) -> bool:
        raise AssertionError("nested key ordering must not run")

    def __hash__(self) -> int:
        raise AssertionError("nested key hashing must not run")


class SensitiveCandidate:
    def __repr__(self) -> str:
        return "authorization: Bearer candidate-secret"


class ExplodingReprCandidate:
    def __repr__(self) -> str:
        raise AssertionError("candidate repr must not be evaluated")


def _pem(label: str) -> str:
    return (
        "-----BEGIN PUBLIC KEY-----\n"
        f"public-material-{label}\n"
        "-----END PUBLIC KEY-----\n"
    )


def _key(key_id: str, label: str | None = None) -> DelegationPublicKey:
    return DelegationPublicKey(
        key_id=key_id,
        algorithm=DelegationKeyAlgorithm.ED25519,
        public_key_pem=_pem(label or key_id),
    )


class WorkloadVerifierKeySetTests(unittest.TestCase):
    def _types(self) -> tuple[type, type]:
        module = importlib.import_module(VERIFIER_KEYS_MODULE)
        return (
            getattr(module, "WorkloadNodeControlVerifierKeySet"),
            getattr(module, "AtomicWorkloadNodeControlVerifierKeySet"),
        )

    def _key_set(self, *keys: DelegationPublicKey) -> object:
        key_set_type, _ = self._types()
        return key_set_type(
            purpose=DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
            public_keys=keys,
        )

    def test_a_a_plus_b_and_b_are_deterministic_exact_snapshots(self) -> None:
        key_set_type, _ = self._types()
        key_a = _key("key-a")
        key_b = _key("key-b")

        a = key_set_type(
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
            (key_a,),
        )
        a_plus_b = key_set_type(
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
            (key_b, key_a),
        )
        b = key_set_type(
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
            (key_b,),
        )

        self.assertIs(a.purpose, DelegationKeyPurpose.WORKLOAD_NODE_CONTROL)
        self.assertEqual(tuple(key.key_id for key in a.public_keys), ("key-a",))
        self.assertEqual(
            tuple(key.key_id for key in a_plus_b.public_keys),
            ("key-a", "key-b"),
        )
        self.assertIs(a_plus_b.public_keys[0], key_a)
        self.assertIs(a_plus_b.public_keys[1], key_b)
        self.assertEqual(tuple(key.key_id for key in b.public_keys), ("key-b",))

    def test_exact_purpose_tuple_key_and_bounds_are_closed(self) -> None:
        key_set_type, _ = self._types()
        key = _key("key-a")

        with self.assertRaisesRegex(
            TypeError,
            "workload verifier key set purpose must be DelegationKeyPurpose",
        ):
            key_set_type("workload-node-control", (key,))
        with self.assertRaisesRegex(
            ValueError,
            "workload verifier key set purpose must be workload-node-control",
        ):
            key_set_type(DelegationKeyPurpose.GATEWAY_PROBE, (key,))
        with self.assertRaisesRegex(
            TypeError,
            "workload verifier public_keys must be a tuple",
        ):
            key_set_type(DelegationKeyPurpose.WORKLOAD_NODE_CONTROL, [key])

        for keys in ((), tuple(_key(f"key-{index}") for index in range(17))):
            with self.subTest(size=len(keys)):
                with self.assertRaisesRegex(
                    ValueError,
                    "workload verifier key set must contain one to sixteen keys",
                ):
                    key_set_type(DelegationKeyPurpose.WORKLOAD_NODE_CONTROL, keys)

        for candidate in (object(), PublicKeySubclass("key-a", key.algorithm, _pem("a"))):
            with self.subTest(candidate=type(candidate).__name__):
                with self.assertRaisesRegex(
                    TypeError,
                    "workload verifier keys must be exact DelegationPublicKey values",
                ):
                    key_set_type(
                        DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
                        (candidate,),
                    )

    def test_duplicate_ids_and_fingerprints_are_independently_rejected(self) -> None:
        key_set_type, _ = self._types()
        duplicate_id = (_key("key-a", "first"), _key("key-a", "second"))
        duplicate_fingerprint = (_key("key-a", "shared"), _key("key-b", "shared"))

        with self.assertRaisesRegex(
            ValueError,
            "workload verifier key ids must be unique",
        ):
            key_set_type(
                DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
                duplicate_id,
            )
        with self.assertRaisesRegex(
            ValueError,
            "workload verifier key fingerprints must be unique",
        ):
            key_set_type(
                DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
                duplicate_fingerprint,
            )

    def test_nested_fields_reject_before_caller_behavior_or_repr(self) -> None:
        key_set_type, _ = self._types()
        key = _key("key-a")
        object.__setattr__(key, "key_id", SensitiveText("key-sensitive"))

        with self.assertRaises(TypeError) as raised:
            key_set_type(DelegationKeyPurpose.WORKLOAD_NODE_CONTROL, (key,))

        self.assertEqual(
            str(raised.exception),
            "workload verifier public key fields must use exact core types",
        )
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        self.assertNotIn("nested-key-secret", str(raised.exception))

        for field_name, candidate in (
            ("algorithm", object()),
            ("public_key_pem", SensitiveText(_pem("sensitive"))),
            ("fingerprint_sha256", SensitiveText("f" * 64)),
        ):
            with self.subTest(field_name=field_name):
                mutated = _key("key-b")
                object.__setattr__(mutated, field_name, candidate)
                with self.assertRaisesRegex(
                    TypeError,
                    "workload verifier public key fields must use exact core types",
                ):
                    key_set_type(
                        DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
                        (mutated,),
                    )

    def test_exact_core_shape_and_canonical_identity_are_required(self) -> None:
        key_set_type, _ = self._types()
        cases: list[tuple[str, DelegationPublicKey]] = []

        extra_field = _key("key-extra")
        object.__setattr__(extra_field, "unexpected_material", SensitiveCandidate())
        cases.append(("extra-field", extra_field))

        missing_field = _key("key-missing")
        object.__delattr__(missing_field, "fingerprint_sha256")
        cases.append(("missing-field", missing_field))

        malformed_id = _key("key-id")
        object.__setattr__(malformed_id, "key_id", "NOT-CANONICAL")
        cases.append(("malformed-id", malformed_id))

        forged_fingerprint = _key("key-fingerprint")
        object.__setattr__(forged_fingerprint, "fingerprint_sha256", "0" * 64)
        cases.append(("forged-fingerprint", forged_fingerprint))

        noncanonical_pem = _key("key-pem")
        object.__setattr__(
            noncanonical_pem,
            "public_key_pem",
            noncanonical_pem.public_key_pem.rstrip("\n"),
        )
        cases.append(("noncanonical-pem", noncanonical_pem))

        for identity, candidate in cases:
            with self.subTest(identity=identity):
                with self.assertRaises(TypeError) as raised:
                    key_set_type(
                        DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
                        (candidate,),
                    )
                self.assertEqual(
                    str(raised.exception),
                    "workload verifier public key must be an admitted exact "
                    "DelegationPublicKey",
                )
                self.assertIsNone(raised.exception.__cause__)
                self.assertIsNone(raised.exception.__context__)
                self.assertNotIn("candidate-secret", str(raised.exception))

    def test_value_shape_and_representations_exclude_public_material(self) -> None:
        key_set_type, holder_type = self._types()
        key = _key("key-sensitive", "pem-sensitive")
        key_set = key_set_type(
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
            (key,),
        )
        holder = holder_type(key_set)

        self.assertTrue(key_set_type.__dataclass_params__.frozen)
        self.assertEqual(tuple(field.name for field in fields(key_set_type)), ("purpose", "public_keys"))
        self.assertEqual(key_set_type.__slots__, ("purpose", "public_keys"))
        self.assertFalse(hasattr(key_set, "__dict__"))
        self.assertEqual(holder_type.__slots__, ("_lock", "_snapshot"))
        self.assertFalse(hasattr(holder, "__dict__"))
        self.assertFalse(hasattr(key_set, "descriptor"))
        self.assertFalse(hasattr(key_set, "codec"))

        for rendered in (repr(key_set), repr(holder)):
            with self.subTest(rendered=rendered):
                self.assertNotIn(key.key_id, rendered)
                self.assertNotIn(key.fingerprint_sha256, rendered)
                self.assertNotIn("pem-sensitive", rendered)
                self.assertNotIn("BEGIN PUBLIC KEY", rendered)

    def test_holder_retains_and_replaces_exact_complete_snapshot(self) -> None:
        key_set_type, holder_type = self._types()
        key_a = _key("key-a")
        key_b = _key("key-b")
        a = key_set_type(DelegationKeyPurpose.WORKLOAD_NODE_CONTROL, (key_a,))
        a_plus_b = key_set_type(
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
            (key_a, key_b),
        )
        holder = holder_type(a)

        self.assertIs(holder.snapshot(), a)
        self.assertIs(holder.replace(a_plus_b), a_plus_b)
        self.assertIs(holder.snapshot(), a_plus_b)

        class KeySetSubclass(key_set_type):
            pass

        subclass = KeySetSubclass(
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
            (key_a,),
        )
        for candidate in (SensitiveCandidate(), ExplodingReprCandidate(), subclass):
            with self.subTest(candidate=type(candidate).__name__):
                with self.assertRaisesRegex(
                    TypeError,
                    "atomic workload verifier key set must be "
                    "WorkloadNodeControlVerifierKeySet",
                ):
                    holder_type(candidate)
                with self.assertRaises(TypeError) as raised:
                    holder.replace(candidate)
                self.assertEqual(
                    str(raised.exception),
                    "atomic workload verifier key set must be "
                    "WorkloadNodeControlVerifierKeySet",
                )
                self.assertIsNone(raised.exception.__cause__)
                self.assertIsNone(raised.exception.__context__)
                self.assertNotIn("candidate-secret", str(raised.exception))
                self.assertIs(holder.snapshot(), a_plus_b)

    def test_concurrent_readers_and_writers_observe_only_complete_identities(self) -> None:
        key_set_type, holder_type = self._types()
        key_a = _key("key-a")
        key_b = _key("key-b")
        snapshots = (
            key_set_type(DelegationKeyPurpose.WORKLOAD_NODE_CONTROL, (key_a,)),
            key_set_type(
                DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
                (key_a, key_b),
            ),
            key_set_type(DelegationKeyPurpose.WORKLOAD_NODE_CONTROL, (key_b,)),
        )
        holder = holder_type(snapshots[0])
        barrier = Barrier(6)
        observed: list[object] = []
        published: list[object] = []

        def read_many() -> None:
            barrier.wait()
            for _ in range(2_000):
                observed.append(holder.snapshot())

        def publish(candidate: object) -> None:
            barrier.wait()
            published.append(holder.replace(candidate))

        threads = [Thread(target=read_many) for _ in range(3)]
        threads.extend(Thread(target=publish, args=(candidate,)) for candidate in snapshots[1:])
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(3)
            self.assertFalse(thread.is_alive())

        accepted_ids = {id(snapshot) for snapshot in snapshots}
        self.assertTrue(observed)
        self.assertTrue({id(snapshot) for snapshot in observed}.issubset(accepted_ids))
        self.assertEqual({id(snapshot) for snapshot in published}, {id(snapshots[1]), id(snapshots[2])})
        self.assertIn(id(holder.snapshot()), accepted_ids)

        separate = holder_type(snapshots[0])
        self.assertIs(separate.snapshot(), snapshots[0])
        self.assertIsNot(separate.snapshot(), holder.snapshot())

    def test_replace_lock_body_is_one_reference_publication(self) -> None:
        _, holder_type = self._types()
        tree = ast.parse(textwrap.dedent(inspect.getsource(holder_type.replace)))
        with_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.With)]

        self.assertEqual(len(with_nodes), 1)
        self.assertEqual(len(with_nodes[0].body), 1)
        assignment = with_nodes[0].body[0]
        self.assertIsInstance(assignment, ast.Assign)
        self.assertFalse(
            any(isinstance(node, (ast.Call, ast.Compare)) for node in ast.walk(assignment))
        )

    def test_root_exports_and_source_imports_remain_framework_neutral(self) -> None:
        key_set_type, holder_type = self._types()
        sdk = importlib.import_module("control_plane_kit_server_sdk")

        self.assertIs(sdk.WorkloadNodeControlVerifierKeySet, key_set_type)
        self.assertIs(sdk.AtomicWorkloadNodeControlVerifierKeySet, holder_type)
        self.assertEqual(key_set_type.__module__, VERIFIER_KEYS_MODULE)
        self.assertEqual(holder_type.__module__, VERIFIER_KEYS_MODULE)

        forbidden = {
            "cloudflare",
            "control_plane_kit_operations",
            "control_plane_kit_interpreters",
            "control_plane_kit_secrets",
            "control_plane_kit_servers",
            "cryptography",
            "docker",
            "fastapi",
            "jwt",
            "psycopg",
        }
        findings: list[str] = []
        for path in sorted(PACKAGE_ROOT.glob("*.py")):
            permitted = {"jwt"} if path.name == "verification.py" else set()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".", 1)[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    roots = {node.module.split(".", 1)[0]}
                else:
                    roots = set()
                findings.extend(sorted(roots & (forbidden - permitted)))
        self.assertEqual(findings, [])

    def test_docs_assign_integrity_provenance_and_verifier_ownership(self) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        decision = (
            REPOSITORY_ROOT
            / "docs"
            / "decisions"
            / "0008-workload-verifier-public-material.md"
        ).read_text(encoding="utf-8")

        for required in (
            "WorkloadNodeControlVerifierKeySet",
            "AtomicWorkloadNodeControlVerifierKeySet",
            "public verification material",
            "process-local",
            "issuer",
            "audience",
            "#1150",
        ):
            with self.subTest(required=required):
                self.assertIn(required, readme + decision)
        for excluded in (
            "proves graph membership",
            "proves provenance",
            "survives process restart",
        ):
            with self.subTest(excluded=excluded):
                self.assertNotIn(excluded, decision)


if __name__ == "__main__":
    unittest.main()
