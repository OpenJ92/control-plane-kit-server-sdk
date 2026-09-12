Source: [src/control_plane_kit_server_sdk/verifier_keys.py](../../../../src/control_plane_kit_server_sdk/verifier_keys.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

Three nominal key-set/atomic-holder families separate workload commands, static surface reads and health reads. The new health family accepts only WORKLOAD_NODE_HEALTH_READ. Each complete snapshot contains 1–16 exact Core DelegationPublicKey values, sorted by independently unique IDs with unique fingerprints. Exact scalar shape and reconstruction reject altered public identity. Existing command/static constructors are unchanged.

Core95452249 public-key construction normalizes lexical public PEM and computes fingerprint congruence; cryptographic parsing and signature admission belong to verification.py. Public configuration is integrity-sensitive and excluded from routine representations. Trusted composition supplies it; there is no issuer-provenance, lifecycle, private-key custody, restart reconstruction or durable rotation guarantee.

Each holder validates its exact nominal set type and publishes one reference under a process-local lock. No old holder/set substitutes for the health family, even with the same PEM. Immutable supplied values and normal Python ownership are assumed; this is not a sandbox against arbitrary object mutation. Health tests cover bounds/separation and in-flight snapshot replacement; legacy tests retain existing concurrency laws.
