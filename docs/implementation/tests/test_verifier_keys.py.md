Source: [tests/test_verifier_keys.py](../../../tests/test_verifier_keys.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The existing command/static key configuration tests retain exact type/purpose, bounds, public identity, atomic replacement, concurrency and redaction assertions. SDK23 only names the new private FastAPI health adapter in the existing narrow allowed framework-import-owner set. No public-key admission assertion or dependency-boundary prohibition is removed. The health dispatcher imports no framework; its optional import boundary is also exercised by the installed verification-extra probe. Source import inventories are not complete transitive or runtime security proofs.

## Behavior and evidence details

These tests exercise deterministic A, A+B and B snapshots, exact purpose/type
admission, canonical nested public material, independent ID/fingerprint
uniqueness and routine representation hiding. Variable-command and surface-read
sets/holders must not substitute for one another.

Concurrent reader/writer witnesses observe complete supplied snapshot identities;
a structural assertion additionally checks the small publication critical
section. Constructor-bypass and hostile-field fixtures test selected rejection
boundaries, not universal protection against arbitrary mutation after
construction. Holder tests cover exact-type admission separately.

Fixture PEM represents the selected Core's lexical contract; these tests do
not establish that every supplied string is a cryptographically usable key,
prove producer provenance, execute a signed grant, or demonstrate durable
rotation. Read [verifier_keys.py](../src/control_plane_kit_server_sdk/verifier_keys.py.md)
and the selected Core owner before extending key assumptions. Large test-file
navigation is based on selected behavioral assertions, not a fresh full audit.
