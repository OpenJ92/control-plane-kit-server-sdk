Source: [src/control_plane_kit_server_sdk/verification.py](../../../../src/control_plane_kit_server_sdk/verification.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This optional module owns two Ed25519 credential-admission objects: variable
READ/APPLY and capability/status surface reads. It imports PyJWT when this module
is imported; the framework-neutral package root does not export these objects.
Public key holders come from [verifier_keys.py](verifier_keys.py.md). Exact
holder/purpose types keep command and surface-read authority families separate.
Each admission reads one complete snapshot and selects exactly one matching
Ed25519 key. Trusted composition supplies issuer, audience, clock and key state;
the verifier does not acquire keys or prove their producer/lifecycle provenance.

Admission first checks exact trusted route input types and compact framing,
canonical base64url segments, duplicate-aware JSON and closed header/grant
profiles. Command credentials have a 12,288-byte ceiling with encoded segment
ceilings 1,024/8,192/1,024; surface credentials use 4,096 and 512/3,840/128.
Structural walking caps depth at 16 and aggregate object members at 64 after
JSON parsing; these are not a streaming parser budget or a count of list items.
Maintained PyJWT then verifies EdDSA signature, issuer and strict audience.
Library time checks are disabled in favor of the supplied clock and Core laws.

Authenticated claims are checked again, decoded through the consumer-selected
Core 0ee72c3 codecs and compared with the protected-header key ID and outer
issuer/audience/time/JTI fields. One exact nonnegative safe integer clock sample
governs the half-open interval: not_before <= now < expires_at. Command admission
checks route operation/variable before reconstructing READ or decoding APPLY's
strict, at-most-16-KiB candidate. Authentication and temporal admission precede
candidate decoding. Core compares complete target/request/codec/digest binding;
surface reads also bind declaration identity and route kind.

The result is an ordinary exact Core request. It is not a durable authority
wrapper, live registry lookup, proof of graph membership or proof that the
receiving application has the same target. Framework adapters own that trusted
target comparison, body extraction, route lookup and invocation. candidate=None
for reads asserts the framework-neutral no-payload input; it does not enforce
HTTP bodylessness. Both verifiers are stateless and may admit a still-valid
credential again. Replay and application mutation live elsewhere.

Ordinary admission failures become fixed categorical errors raised after the
exception handler, omitting candidate/library details and exception links.
Constructors similarly use fixed validation messages and routine representations
omit key/issuer/audience material. Process-control BaseExceptions are not caught
by admit. No provider call, credential issuance, persistence or workload effect
is introduced here. See [verification tests](../../tests/test_verification.py.md)
and decisions [0010](../../../../docs/decisions/0010-signed-workload-node-control-admission.md)
and [0012](../../../../docs/decisions/0012-signed-surface-read-admission.md).
