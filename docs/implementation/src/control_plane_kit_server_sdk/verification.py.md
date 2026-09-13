Source: [src/control_plane_kit_server_sdk/verification.py](../../../../src/control_plane_kit_server_sdk/verification.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The optional owner now admits three disjoint credential families: variable commands, static surface reads and semantic health reads. Base SDK imports stay free of PyJWT/FastAPI. Existing command and surface behavior remains unchanged; surface and health reuse the bounded compact-framing helper with their own ceilings.

Health uses CPK-WORKLOAD-NODE-HEALTH-READ+JWT and the closed workload_node_health_read payload. One exact-purpose atomic snapshot selects one Ed25519 key. Duplicate-aware bounded JSON and canonical base64url inspection precede maintained PyJWT verification; authenticated outer/embedded/header claims must agree. One supplied safe-integer clock and Core's predicate compare half-open time and independently supplied target, runtime, V2 declaration and actual kind. candidate must be exactly None; transport bodylessness belongs to the FastAPI or stdlib adapter.

The selected Core is 95452249d0340707a5cdffe737e34669e9d53165, including its shared public-wire and command/surface changes. Health reconstructs only the candidate from authenticated claims, never expected local authority. It returns ordinary Core NodeHealthReadRequest, adds no callback, replay store, provider effect, key custody or graph/attempt approval proof. Repeated admission preserves observation identity.

Maximum canonical compact health material is 4178 bytes; admission bounds total4608 and segments512/3968/128 also permit bounded JSON whitespace. The shared walker retains depth16/member64 limits. Ordinary failures become fixed errors raised outside handlers without exception links; BaseException propagates. Reprs omit key/issuer/audience. SDK #23 owns callback and FastAPI composition. See decision0015 and the health admission tests; owning gate results belong in the PR, not inferred from this note.

## Behavior and evidence details

Admission first checks exact trusted route input types and compact framing,
canonical base64url segments, duplicate-aware JSON and closed header/grant
profiles. Command credentials have a 12,288-byte ceiling with encoded segment
ceilings 1,024/8,192/1,024; surface credentials use 4,096 and 512/3,840/128.
Structural walking caps depth at 16 and aggregate object members at 64 after
JSON parsing; these are not a streaming parser budget or a count of list items.
Maintained PyJWT then verifies EdDSA signature, issuer and strict audience.
Library time checks are disabled in favor of the supplied clock and Core laws.

Authenticated claims are checked again, decoded through the consumer-selected
Core 95452249 codecs and compared with the protected-header key ID and outer
issuer/audience/time/JTI fields. One exact nonnegative safe integer clock sample
governs the half-open interval: not_before <= now < expires_at. Command admission
checks route operation/variable before reconstructing READ or decoding APPLY's
strict, at-most-16-KiB candidate. Authentication and temporal admission precede
candidate decoding. Core compares complete target/request/codec/digest binding;
surface reads also bind declaration identity and route kind. Health admission additionally takes independent installed target, runtime and V2 declaration, as described above.

Ordinary admission failures become fixed categorical errors raised after the
exception handler, omitting candidate/library details and exception links.
Constructors similarly use fixed validation messages and routine representations
omit key/issuer/audience material. Process-control BaseExceptions are not caught
by admit. No provider call, credential issuance, persistence or workload effect
is introduced here. See [verification tests](../../tests/test_verification.py.md)
and decisions [0010](../../../../docs/decisions/0010-signed-workload-node-control-admission.md)
and [0012](../../../../docs/decisions/0012-signed-surface-read-admission.md).
