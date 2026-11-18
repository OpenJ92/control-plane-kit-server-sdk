Source: [tests/receiver_fixtures.py](../../../tests/receiver_fixtures.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

SDK43 successor fixtures construct accepted Core receiver configurations, separate authority contexts, health/surface/command requests and purpose-separated ephemeral test signing keys. Existing maintained test signing helpers produce real compact signatures. No key or token is persisted. The fixture does not allocate identities, simulate Operations acceptance, install trust in an external process or implement a verifier.

Health-only, mixed and variable-only declared shapes use Core's exact verifier-family contract. A temporary regular0444 file exercises the ordinary SDK loader. New SDK assertions must follow successful Core construction/roundtrip; a malformed fixture is not causal evidence of missing SDK behavior. This target checkpoint has not run.
