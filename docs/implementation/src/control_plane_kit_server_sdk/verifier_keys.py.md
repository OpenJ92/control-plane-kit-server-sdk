Source: [src/control_plane_kit_server_sdk/verifier_keys.py](../../../../src/control_plane_kit_server_sdk/verifier_keys.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

Three nominal key-set/atomic-holder families separate workload commands, static surface reads and health reads. The new health family accepts only WORKLOAD_NODE_HEALTH_READ. Each complete snapshot contains 1–16 exact Core DelegationPublicKey values, sorted by independently unique IDs with unique fingerprints. Exact scalar shape and reconstruction reject altered public identity. Existing command/static constructors are unchanged.

Core95452249 public-key construction normalizes lexical public PEM and computes fingerprint congruence; cryptographic parsing and signature admission belong to verification.py. Public configuration is integrity-sensitive and excluded from routine representations. Trusted composition supplies it; there is no issuer-provenance, lifecycle, private-key custody, restart reconstruction or durable rotation guarantee.

Each holder validates its exact nominal set type and publishes one reference under a process-local lock. No old holder/set substitutes for the health family, even with the same PEM. Immutable supplied values and normal Python ownership are assumed; this is not a sandbox against arbitrary object mutation. Health tests cover bounds/separation and in-flight snapshot replacement; legacy tests retain existing concurrency laws.

## Behavior and evidence details

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
