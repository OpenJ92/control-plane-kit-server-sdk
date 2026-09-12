Source: [tests/test_health_verification.py](../../../tests/test_health_verification.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

Eight public behavior tests use generated test-only Ed25519 keys and maintained PyJWT. They admit both health kinds with exact reconstructed request/canonical bytes, prove the real4178-byte maximum and valid bounded-whitespace segment ceilings, and deny representative malformed/duplicate/noncanonical/profile/signature/outer-claim/digest/local-context/time inputs. Candidate values other than None reject before the clock.

Other cases prove health/old holder and signed-family separation even with common PEM, 1–16 unique supplied snapshots, altered fingerprint rejection, one in-flight snapshot across replacement, one clock per successful admission, repeatability without a replay cache, and fixed cause/context-free errors with BaseException propagation. Instrumented PyJWT calls retain real verification; fixtures never replace it with successful fake admission. No credential/private material is checked in.

Oversize tests use real re-signed JSON for header/payload limits and canonically framed signature/aggregate oversize values. Zero maintained-admission calls isolate these limits from later signature failure; encoded lengths514/3970/130 are the first reachable lengths above their caps, and aggregate4609 fits the separate segment caps. Duplicate nested JSON is assembled explicitly with existing raw-object helpers so the actual verifier receives duplicate bytes.

These are SDK admission tests, not HTTP-body enforcement, callback-zero, gateway-zero-network, durable rotation or live-provider evidence. #23 owns callbacks and actual FastAPI framing. Existing complete legacy tests and installed probes must pass under the deliberately selected Core95452249 pin. No exhaustive Core comparison matrix is copied.
