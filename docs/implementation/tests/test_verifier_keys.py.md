Source: [tests/test_verifier_keys.py](../../../tests/test_verifier_keys.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

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
