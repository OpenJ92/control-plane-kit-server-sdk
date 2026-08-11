"""Bounded process-local public verification material for workload grants."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from control_plane_kit_core import (
    DelegationKeyAlgorithm,
    DelegationKeyPurpose,
    DelegationPublicKey,
)


_MAX_PUBLIC_KEYS = 16
_PUBLIC_KEY_FIELD_NAMES = (
    "algorithm",
    "fingerprint_sha256",
    "key_id",
    "public_key_pem",
)


@dataclass(frozen=True, slots=True)
class WorkloadNodeControlVerifierKeySet:
    """One complete supplied snapshot of workload verification keys."""

    purpose: DelegationKeyPurpose
    public_keys: tuple[DelegationPublicKey, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.purpose) is not DelegationKeyPurpose:
            raise TypeError(
                "workload verifier key set purpose must be DelegationKeyPurpose"
            )
        if self.purpose is not DelegationKeyPurpose.WORKLOAD_NODE_CONTROL:
            raise ValueError(
                "workload verifier key set purpose must be workload-node-control"
            )
        if type(self.public_keys) is not tuple:
            raise TypeError("workload verifier public_keys must be a tuple")
        if not 1 <= len(self.public_keys) <= _MAX_PUBLIC_KEYS:
            raise ValueError(
                "workload verifier key set must contain one to sixteen keys"
            )
        if any(type(key) is not DelegationPublicKey for key in self.public_keys):
            raise TypeError(
                "workload verifier keys must be exact DelegationPublicKey values"
            )
        if any(not _has_exact_public_key_shape(key) for key in self.public_keys):
            raise TypeError(
                "workload verifier public key must be an admitted exact "
                "DelegationPublicKey"
            )
        if any(
            type(key.key_id) is not str
            or type(key.algorithm) is not DelegationKeyAlgorithm
            or type(key.public_key_pem) is not str
            or type(key.fingerprint_sha256) is not str
            for key in self.public_keys
        ):
            raise TypeError(
                "workload verifier public key fields must use exact core types"
            )
        if any(not _is_canonical_public_key(key) for key in self.public_keys):
            raise TypeError(
                "workload verifier public key must be an admitted exact "
                "DelegationPublicKey"
            )

        ordered = tuple(sorted(self.public_keys, key=lambda key: key.key_id))
        if len({key.key_id for key in ordered}) != len(ordered):
            raise ValueError("workload verifier key ids must be unique")
        if len({key.fingerprint_sha256 for key in ordered}) != len(ordered):
            raise ValueError("workload verifier key fingerprints must be unique")
        object.__setattr__(self, "public_keys", ordered)


@dataclass(frozen=True, slots=True)
class WorkloadNodeControlSurfaceReadVerifierKeySet:
    """One complete supplied snapshot of surface-read verification keys."""

    purpose: DelegationKeyPurpose
    public_keys: tuple[DelegationPublicKey, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.purpose) is not DelegationKeyPurpose:
            raise TypeError(
                "surface-read verifier key set purpose must be DelegationKeyPurpose"
            )
        if (
            self.purpose
            is not DelegationKeyPurpose.WORKLOAD_NODE_CONTROL_SURFACE_READ
        ):
            raise ValueError(
                "surface-read verifier key set purpose must be "
                "workload-node-control-surface-read"
            )
        if type(self.public_keys) is not tuple:
            raise TypeError("surface-read verifier public_keys must be a tuple")
        if not 1 <= len(self.public_keys) <= _MAX_PUBLIC_KEYS:
            raise ValueError(
                "surface-read verifier key set must contain one to sixteen keys"
            )
        if any(type(key) is not DelegationPublicKey for key in self.public_keys):
            raise TypeError(
                "surface-read verifier keys must be exact DelegationPublicKey values"
            )
        if any(not _has_exact_public_key_shape(key) for key in self.public_keys):
            raise TypeError(
                "surface-read verifier public key must be an admitted exact "
                "DelegationPublicKey"
            )
        if any(
            type(key.key_id) is not str
            or type(key.algorithm) is not DelegationKeyAlgorithm
            or type(key.public_key_pem) is not str
            or type(key.fingerprint_sha256) is not str
            for key in self.public_keys
        ):
            raise TypeError(
                "surface-read verifier public key fields must use exact core types"
            )
        if any(not _is_canonical_public_key(key) for key in self.public_keys):
            raise TypeError(
                "surface-read verifier public key must be an admitted exact "
                "DelegationPublicKey"
            )

        ordered = tuple(sorted(self.public_keys, key=lambda key: key.key_id))
        if len({key.key_id for key in ordered}) != len(ordered):
            raise ValueError("surface-read verifier key ids must be unique")
        if len({key.fingerprint_sha256 for key in ordered}) != len(ordered):
            raise ValueError("surface-read verifier key fingerprints must be unique")
        object.__setattr__(self, "public_keys", ordered)


def _has_exact_public_key_shape(key: DelegationPublicKey) -> bool:
    namespace = key.__dict__
    if type(namespace) is not dict:
        return False
    field_names = tuple(namespace)
    return (
        all(type(field_name) is str for field_name in field_names)
        and tuple(sorted(field_names)) == _PUBLIC_KEY_FIELD_NAMES
    )


def _is_canonical_public_key(key: DelegationPublicKey) -> bool:
    try:
        canonical = DelegationPublicKey(
            key_id=key.key_id,
            algorithm=key.algorithm,
            public_key_pem=key.public_key_pem,
        )
    except (TypeError, ValueError):
        return False
    return (
        canonical.key_id == key.key_id
        and canonical.algorithm is key.algorithm
        and canonical.public_key_pem == key.public_key_pem
        and canonical.fingerprint_sha256 == key.fingerprint_sha256
    )


class AtomicWorkloadNodeControlVerifierKeySet:
    """Atomically publish one complete process-local key-set snapshot."""

    __slots__ = ("_lock", "_snapshot")

    def __init__(self, initial: WorkloadNodeControlVerifierKeySet) -> None:
        self._require_key_set(initial)
        self._lock = Lock()
        self._snapshot = initial

    def snapshot(self) -> WorkloadNodeControlVerifierKeySet:
        with self._lock:
            snapshot = self._snapshot
        return snapshot

    def replace(
        self,
        candidate: WorkloadNodeControlVerifierKeySet,
    ) -> WorkloadNodeControlVerifierKeySet:
        self._require_key_set(candidate)
        with self._lock:
            self._snapshot = candidate
        return candidate

    @staticmethod
    def _require_key_set(candidate: object) -> None:
        if type(candidate) is not WorkloadNodeControlVerifierKeySet:
            raise TypeError(
                "atomic workload verifier key set must be "
                "WorkloadNodeControlVerifierKeySet"
            )


class AtomicWorkloadNodeControlSurfaceReadVerifierKeySet:
    """Atomically publish one complete surface-read key-set snapshot."""

    __slots__ = ("_lock", "_snapshot")

    def __init__(
        self,
        initial: WorkloadNodeControlSurfaceReadVerifierKeySet,
    ) -> None:
        self._require_key_set(initial)
        self._lock = Lock()
        self._snapshot = initial

    def snapshot(self) -> WorkloadNodeControlSurfaceReadVerifierKeySet:
        with self._lock:
            snapshot = self._snapshot
        return snapshot

    def replace(
        self,
        candidate: WorkloadNodeControlSurfaceReadVerifierKeySet,
    ) -> WorkloadNodeControlSurfaceReadVerifierKeySet:
        self._require_key_set(candidate)
        with self._lock:
            self._snapshot = candidate
        return candidate

    @staticmethod
    def _require_key_set(candidate: object) -> None:
        if type(candidate) is not WorkloadNodeControlSurfaceReadVerifierKeySet:
            raise TypeError(
                "atomic surface-read verifier key set must be "
                "WorkloadNodeControlSurfaceReadVerifierKeySet"
            )


__all__ = [
    "AtomicWorkloadNodeControlSurfaceReadVerifierKeySet",
    "AtomicWorkloadNodeControlVerifierKeySet",
    "WorkloadNodeControlSurfaceReadVerifierKeySet",
    "WorkloadNodeControlVerifierKeySet",
]
