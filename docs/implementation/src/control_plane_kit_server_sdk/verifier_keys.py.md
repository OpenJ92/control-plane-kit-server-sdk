Source: [src/control_plane_kit_server_sdk/verifier_keys.py](../../../../src/control_plane_kit_server_sdk/verifier_keys.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This owner admits complete process-local public-key snapshots for two distinct
purposes: variable commands and surface reads. Their exact key-set/holder types
are not interchangeable. Each set contains one to sixteen exact Core public
keys, ordered by key ID with independently unique IDs and fingerprints.

Construction checks exact instance fields and scalar types, then reconstructs
each selected Core DelegationPublicKey and compares normalized PEM and
fingerprint. The consumer's Core declaration is in
[pyproject.toml](../../pyproject.toml.md). At the selected Core version this is
lexical public-PEM normalization and digest congruence, not cryptographic key
parsing or issuer/audience/provenance validation. Actual signed verification
belongs to verification.py.

Each holder publishes one supplied snapshot reference under its private lock.
Readers obtain either a complete old or new snapshot. Holder admission checks
the exact key-set type; it does not rerun the key-set constructor or defend
against every forged/mutated Python object. Trusted composition supplies the
initial/replacement values. Public material remains explicitly accessible to
verification while routine key-set/holder representations omit it.

[Decision 0008](../../../../docs/decisions/0008-workload-verifier-public-material.md)
records this ownership. There is no durable rotation lifecycle, restart
reconstruction, distributed synchronization, credential custody or authority
grant. The [key tests](../../tests/test_verifier_keys.py.md) keep shape,
publication and signature-admission evidence distinct.
