Source: [tests/test_health_verification.py](../../../tests/test_health_verification.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

Eight public behavior tests use generated test-only Ed25519 keys and maintained PyJWT. They admit both health kinds with exact reconstructed request/canonical bytes, prove the real4178-byte maximum and valid bounded-whitespace segment ceilings, and deny representative malformed/duplicate/noncanonical/profile/signature/outer-claim/digest/local-context/time inputs. Candidate values other than None reject before the clock.

Other cases prove health/old holder and signed-family separation even with common PEM, 1–16 unique supplied snapshots, altered fingerprint rejection, one in-flight snapshot across replacement, one clock per successful admission, repeatability without a replay cache, and fixed cause/context-free errors with BaseException propagation. Instrumented PyJWT calls retain real verification; fixtures never replace it with successful fake admission. No credential/private material is checked in.

Oversize tests use real re-signed JSON for header/payload limits and canonically framed signature/aggregate oversize values. Zero maintained-admission calls isolate these limits from later signature failure; encoded lengths514/3970/130 are the first reachable lengths above their caps, and aggregate4609 fits the separate segment caps. Duplicate nested JSON is assembled explicitly with existing raw-object helpers so the actual verifier receives duplicate bytes.

These are SDK admission tests, not HTTP-body enforcement, callback-zero, gateway-zero-network, durable rotation or live-provider evidence. #23 owns callbacks and actual FastAPI framing. Existing complete translated receiver tests and installed probes must pass under the deliberately selected Core 1f28d009 pin. No exhaustive Core comparison matrix is copied.

SDK #43 uses receiver health V2; runtime is inside target and signed authority
context is preserved separately. Independent local negatives cover receiver ID
plus workspace/runtime/node/socket and declaration. The reachable maximum uses
128-character target/request fields with authority IDs of lengths1/25, reaching
request1083 and grant2107. All prior segment/aggregate overflow and signed
whitespace cases remain; no bound is enlarged.

Candidate51dad05 gate36886008866 exposed one missed cross-family call: both
command/surface verifier branches now receive independently constructed local
target/declaration fixtures. This restores the existing precise SDK refusal
assertions instead of failing at missing Python keyword arguments. North's
PR44 release5934956351 authorizes this bounded test-only correction.
