# Decision 0015: Dedicated signed health-read admission

Status: Implemented for SDK #22; owning validation and independent source review
are recorded in [PR #24](https://github.com/OpenJ92/control-plane-kit-server-sdk/pull/24).

Issue #22 is the admission child of SDK #20. Its accepted design separates
credentials from callback/HTTP effects in #23. Core is deliberately selected at
`95452249d0340707a5cdffe737e34669e9d53165`; metadata and exact dependency preflight
agree, and old coordinates remain rejected. The change includes shared public
wire and command/surface evolution since the old pin, so the full SDK suite and
installed probes are required compatibility evidence.

`Ed25519WorkloadNodeHealthReadVerifier` belongs to optional `verification.py`.
The base root exports only the additional nominal health public-key set and
atomic holder. Key configuration is bounded to 1–16 canonical public values
with distinct key IDs and fingerprints. It represents supplied process-local
material, not issuer provenance, durable rotation or key custody.

The credential type is `CPK-WORKLOAD-NODE-HEALTH-READ+JWT`, with exact header
alg/kid/typ and payload iss/aud/iat/nbf/exp/jti/workload_node_health_read. The
embedded Core grant requires its dedicated profile and purpose. Existing command,
static-read and gateway authority cannot substitute, even with the same key
material. There is no public generic verifier registry.

One complete key snapshot selects one Ed25519 key; maintained PyJWT verifies
signature, issuer and strict audience. Shared duplicate-aware JSON and canonical
base64url framing remain bounded. After authenticated outer/embedded/header
congruence, one supplied clock and the merged Core predicate establish the
half-open interval and exact independent local target/runtime/V2 declaration/
route-kind binding. Signed self-consistency supplies a candidate, not authority.
The caller must supply expected context from trusted installed composition.
`candidate=None` is mandatory and is only a neutral no-payload assertion; an
HTTP owner must separately prove bodylessness before calling admission.

The maximum canonical signed credential is 4178 bytes: header194 -> encoded259,
payload2873 -> encoded3831, Ed25519 signature64 -> encoded86, two separators.
Admission caps are aggregate4608 and encoded segments512/3968/128, also allowing
bounded JSON whitespace. They are separate ceilings, not arbitrary new grant
fields. The Core grant remains at most2107 bytes. The original static-read4096
ceiling remains unchanged. Actual owning tests, not arithmetic alone, must prove
real signed maximum admission and malformed-bound rejection.

Every ordinary admission failure is one fixed cause/context-free
`WorkloadNodeHealthReadVerificationError`; repr excludes key/issuer/audience
material. BaseException propagates. Successful admission returns ordinary exact
Core request data, neither an authority wrapper nor proof of current graph or
attempt approval. A still-valid credential may be admitted repeatedly without
creating another observation identity. There is no replay cache or command ledger.

Security and operational boundary: no callback, HTTP listener/route, provider
call, signing service, private material, schema, persistence, image or runtime
mutation is introduced. SDK #23 must capture independent local composition,
admit before invoking any protected callback, derive Core result binding and
atomically compose health-only/mixed routes with the old four-route installer.
Gateway zero-outbound-HTTP denial is a separate owner law; SDK admission alone
does not prove it. Product/native/live work remains outside these SDK children.

Tests target real generated test-key signatures, key-purpose separation,
independent locality, strict framing/profile/claims, temporal boundaries,
snapshot/clock use and redacted errors. Legacy assertions are retained apart
from additive export inventories and the intentional dependency coordinate.
Validation uses only ordinary Docker-backed `./test.sh`; no mandatory failing
suite ceremony or alternate harness. Source, installed-package, composition,
image and live evidence remain distinct.

At source/test head `ec3f2b6fa0a7d188e73c963af4ae97f721987e0f`, the ordinary
pinned gate passed all24 policy and166 package tests, compile and all three
installed-package probe phases. Hosted CI and Meridian's independent source/
test-integrity review passed on that same head. The initial4eaaf397 gate had one
new duplicate-JSON fixture construction error, corrected without production or
legacy-law changes; its failure remains recorded on the PR without behavioral-red
credit. These are SDK package/installed proofs, not callback, HTTP or live proofs.
