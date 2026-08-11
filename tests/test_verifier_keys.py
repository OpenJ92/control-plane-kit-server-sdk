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
from control_plane_kit_server_sdk.verifier_keys import (
    AtomicWorkloadNodeControlVerifierKeySet,
    WorkloadNodeControlVerifierKeySet,
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
            permitted: set[str] = set()
            if path.name == "verification.py":
                permitted.add("jwt")
            if path.name == "_fastapi_variable_routes.py":
                permitted.add("fastapi")
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


class SurfaceReadVerifierKeySetTests(unittest.TestCase):
    def _types(self) -> tuple[type, type]:
        module = importlib.import_module(VERIFIER_KEYS_MODULE)
        try:
            return (
                module.WorkloadNodeControlSurfaceReadVerifierKeySet,
                module.AtomicWorkloadNodeControlSurfaceReadVerifierKeySet,
            )
        except AttributeError:
            self.fail("surface-read verifier key types are not implemented")

    def _key_set(self, *keys: DelegationPublicKey):
        key_set_type, _ = self._types()
        return key_set_type(
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
            keys,
        )

    def test_surface_key_set_is_exact_bounded_sorted_and_purpose_closed(self) -> None:
        key_set_type, holder_type = self._types()
        key_a = _key("shared-key-a")
        key_b = _key("shared-key-b")
        key_set = key_set_type(
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
            (key_b, key_a),
        )
        holder = holder_type(key_set)

        self.assertTrue(key_set_type.__dataclass_params__.frozen)
        self.assertEqual(
            tuple(field.name for field in fields(key_set_type)),
            ("purpose", "public_keys"),
        )
        self.assertEqual(key_set_type.__slots__, ("purpose", "public_keys"))
        self.assertEqual(
            tuple(key.key_id for key in key_set.public_keys),
            ("shared-key-a", "shared-key-b"),
        )
        self.assertEqual(holder_type.__slots__, ("_lock", "_snapshot"))
        self.assertFalse(hasattr(key_set, "__dict__"))
        self.assertFalse(hasattr(holder, "__dict__"))

        for purpose in (
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
            DelegationKeyPurpose.GATEWAY_PROBE,
        ):
            with self.subTest(purpose=purpose):
                with self.assertRaisesRegex(
                    ValueError,
                    "surface-read verifier key set purpose must be "
                    "workload-node-control-surface-read",
                ):
                    key_set_type(purpose, (key_a,))

        for keys in ((), tuple(_key(f"key-{index}") for index in range(17))):
            with self.subTest(size=len(keys)):
                with self.assertRaisesRegex(
                    ValueError,
                    "surface-read verifier key set must contain one to sixteen keys",
                ):
                    key_set_type(
                        DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
                        keys,
                    )

    def test_command_and_surface_key_sets_and_holders_never_substitute(self) -> None:
        surface_key_set_type, surface_holder_type = self._types()
        key = _key("shared-key")
        surface = surface_key_set_type(
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
            (key,),
        )
        command = WorkloadNodeControlVerifierKeySet(
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL,
            (key,),
        )
        surface_holder = surface_holder_type(surface)
        command_holder = AtomicWorkloadNodeControlVerifierKeySet(command)

        with self.assertRaises(TypeError) as raised:
            surface_holder_type(command)
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        with self.assertRaises(TypeError):
            surface_holder.replace(command)
        with self.assertRaises(TypeError):
            AtomicWorkloadNodeControlVerifierKeySet(surface)
        with self.assertRaises(TypeError):
            command_holder.replace(surface)
        self.assertIs(surface_holder.snapshot(), surface)
        self.assertIs(command_holder.snapshot(), command)

    def test_surface_key_set_inherits_exact_public_material_admission(self) -> None:
        key_set_type, _ = self._types()
        key = _key("surface-key")

        with self.assertRaisesRegex(
            TypeError,
            "surface-read verifier key set purpose must be DelegationKeyPurpose",
        ):
            key_set_type("workload-node-control-surface-read", (key,))
        with self.assertRaisesRegex(
            TypeError,
            "surface-read verifier public_keys must be a tuple",
        ):
            key_set_type(
                DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
                [key],
            )

        class PublicKeySubclass(DelegationPublicKey):
            pass

        subclass = PublicKeySubclass(
            "surface-subclass",
            key.algorithm,
            _pem("subclass"),
        )
        with self.assertRaisesRegex(
            TypeError,
            "surface-read verifier keys must be exact DelegationPublicKey values",
        ):
            key_set_type(
                DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
                (subclass,),
            )

        malformed: list[DelegationPublicKey] = []
        extra = _key("surface-extra")
        object.__setattr__(extra, "unexpected_material", SensitiveCandidate())
        malformed.append(extra)
        missing = _key("surface-missing")
        object.__delattr__(missing, "fingerprint_sha256")
        malformed.append(missing)
        bad_id = _key("surface-id")
        object.__setattr__(bad_id, "key_id", "NOT-CANONICAL")
        malformed.append(bad_id)
        bad_fingerprint = _key("surface-fingerprint")
        object.__setattr__(bad_fingerprint, "fingerprint_sha256", "0" * 64)
        malformed.append(bad_fingerprint)
        bad_pem = _key("surface-pem")
        object.__setattr__(bad_pem, "public_key_pem", bad_pem.public_key_pem.rstrip("\n"))
        malformed.append(bad_pem)
        for identity, candidate in enumerate(malformed):
            with self.subTest(malformed=identity):
                with self.assertRaises(TypeError) as raised:
                    key_set_type(
                        DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
                        (candidate,),
                    )
                self.assertIsNone(raised.exception.__cause__)
                self.assertIsNone(raised.exception.__context__)
                self.assertNotIn("candidate-secret", str(raised.exception))

        nested = _key("surface-nested")
        object.__setattr__(nested, "key_id", SensitiveText("surface-nested"))
        with self.assertRaises(TypeError) as raised:
            key_set_type(
                DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
                (nested,),
            )
        self.assertEqual(
            str(raised.exception),
            "surface-read verifier public key fields must use exact core types",
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
                mutated = _key(f"surface-{field_name}")
                object.__setattr__(mutated, field_name, candidate)
                with self.assertRaisesRegex(
                    TypeError,
                    "surface-read verifier public key fields must use exact core types",
                ):
                    key_set_type(
                        DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
                        (mutated,),
                    )

        duplicate_id = (
            _key("surface-duplicate", "first"),
            _key("surface-duplicate", "second"),
        )
        duplicate_fingerprint = (
            _key("surface-a", "shared"),
            _key("surface-b", "shared"),
        )
        with self.assertRaisesRegex(
            ValueError,
            "surface-read verifier key ids must be unique",
        ):
            key_set_type(
                DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
                duplicate_id,
            )
        with self.assertRaisesRegex(
            ValueError,
            "surface-read verifier key fingerprints must be unique",
        ):
            key_set_type(
                DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
                duplicate_fingerprint,
            )

    def test_surface_holder_rejects_invalid_values_and_preserves_snapshot(self) -> None:
        key_set_type, holder_type = self._types()
        accepted = self._key_set(_key("surface-key"))
        holder = holder_type(accepted)

        class KeySetSubclass(key_set_type):
            pass

        subclass = KeySetSubclass(
            DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ,
            (_key("surface-subclass"),),
        )
        for candidate in (
            SensitiveCandidate(),
            ExplodingReprCandidate(),
            subclass,
        ):
            with self.subTest(candidate=type(candidate).__name__):
                with self.assertRaises(TypeError):
                    holder_type(candidate)
                with self.assertRaises(TypeError) as raised:
                    holder.replace(candidate)
                self.assertEqual(
                    str(raised.exception),
                    "atomic surface-read verifier key set must be "
                    "WorkloadNodeControlSurfaceReadVerifierKeySet",
                )
                self.assertIsNone(raised.exception.__cause__)
                self.assertIsNone(raised.exception.__context__)
                self.assertNotIn("candidate-secret", str(raised.exception))
                self.assertIs(holder.snapshot(), accepted)

    def test_surface_replace_lock_body_is_one_reference_publication(self) -> None:
        _, holder_type = self._types()
        tree = ast.parse(textwrap.dedent(inspect.getsource(holder_type.replace)))
        with_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.With)]

        self.assertEqual(len(with_nodes), 1)
        self.assertEqual(len(with_nodes[0].body), 1)
        assignment = with_nodes[0].body[0]
        self.assertIsInstance(assignment, ast.Assign)
        self.assertFalse(
            any(
                isinstance(node, (ast.Call, ast.Compare))
                for node in ast.walk(assignment)
            )
        )

    def test_surface_holder_rotation_is_atomic_and_repr_redacted(self) -> None:
        _, holder_type = self._types()
        key_a = _key("surface-key-a")
        key_b = _key("surface-key-b")
        snapshots = (
            self._key_set(key_a),
            self._key_set(key_a, key_b),
            self._key_set(key_b),
        )
        holder = holder_type(snapshots[0])
        barrier = Barrier(6)
        observed: list[object] = []
        published: list[object] = []
        failures: list[BaseException] = []

        def read_many() -> None:
            barrier.wait()
            for _ in range(2_000):
                observed.append(holder.snapshot())

        def publish(candidate: object) -> None:
            barrier.wait()
            try:
                published.append(holder.replace(candidate))
            except BaseException as error:
                failures.append(error)

        threads = [Thread(target=read_many) for _ in range(3)]
        threads.extend(
            Thread(target=publish, args=(candidate,))
            for candidate in snapshots[1:]
        )
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(3)
            self.assertFalse(thread.is_alive())

        accepted = {id(snapshot) for snapshot in snapshots}
        self.assertEqual(failures, [])
        self.assertTrue(observed)
        self.assertTrue({id(value) for value in observed}.issubset(accepted))
        self.assertEqual(
            {id(value) for value in published},
            {id(snapshots[1]), id(snapshots[2])},
        )
        for rendered in (repr(snapshots[1]), repr(holder)):
            for key in (key_a, key_b):
                self.assertNotIn(key.key_id, rendered)
                self.assertNotIn(key.fingerprint_sha256, rendered)
                self.assertNotIn(key.public_key_pem, rendered)

    def test_surface_key_types_are_root_exported_without_crypto_or_outer_imports(self) -> None:
        key_set_type, holder_type = self._types()
        sdk = importlib.import_module("control_plane_kit_server_sdk")

        self.assertIs(
            sdk.WorkloadNodeControlSurfaceReadVerifierKeySet,
            key_set_type,
        )
        self.assertIs(
            sdk.AtomicWorkloadNodeControlSurfaceReadVerifierKeySet,
            holder_type,
        )
        self.assertIn("WorkloadNodeControlSurfaceReadVerifierKeySet", sdk.__all__)
        self.assertIn(
            "AtomicWorkloadNodeControlSurfaceReadVerifierKeySet",
            sdk.__all__,
        )

        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        decision = (
            REPOSITORY_ROOT
            / "docs"
            / "decisions"
            / "0012-signed-surface-read-admission.md"
        )
        self.assertTrue(decision.is_file())
        combined = readme + decision.read_text(encoding="utf-8")
        for required in (
            "WorkloadNodeControlSurfaceReadVerifierKeySet",
            "WORKLOAD_NODE_CONTROL_SURFACE_READ",
            "process-local",
            "public verification material",
            "#1507",
        ):
            self.assertIn(required, combined)


if __name__ == "__main__":
    unittest.main()
