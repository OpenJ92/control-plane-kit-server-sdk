# Decision 0016: Closed health dispatch and atomic FastAPI composition

Status: Implemented for SDK #23; owning evidence and independent review belong
in its PR before acceptance. Consumes merged SDK #22 at947eaaf and unchanged
Core95452249d0340707a5cdffe737e34669e9d53165.

`WorkloadNodeHealthReadDispatcher` is an optional verification-extra owner in
health.py. Frozen local target/runtime/V2 declaration and verifier form its
receiving context. Liveness/readiness are the only callback names; supplied
synchronous callables must support no-argument invocation and exactly cover
declared kinds. Signature inspection validates invocation shape without calling
the workload. Uninspectable/async callbacks fail configuration with a bounded
error. Trusted callback introspection is not a sandbox or a generic plugin API.

Each read invokes the accepted verifier with captured independent local context
and actual route kind before selecting one callback. Only exact Core
NodeHealthReadOutcome values become Core NodeHealthReadResult data derived from
the admitted request/declaration. Ordinary callback or result errors become one
fixed cause/context-free dispatch error. BaseException propagates. An accidentally
returned native coroutine is closed without running it to avoid an unawaited
warning; no async callback protocol is added. Workloads own health meaning and
bounded dependency reads, not SDK polling or invented checks.

The one existing `install_cpk_control_routes` now optionally consumes a health
dispatcher. It retains a required static surface verifier for all shapes:

| Declaration | Routes | Command authority/replay |
| --- | --- | --- |
| Legacy V1 | Existing capabilities/status/variable GET/command POST | Existing required verifier and replay |
| Health-only V2 | Capabilities/status/health GET | None; command verifier/nonempty variables reject |
| Mixed V2 | Existing four plus health GET | Existing verifier/replay for variables only |

V2 requires a dispatcher with equal installed target and declaration. V1 rejects
one. Configuration checks, collision classification, variable snapshots, route
construction and marking all precede one host route-list publication. Legacy
validation precedence, partial variable-registry behavior, existing route
identities, closed collision rules and startup timing remain. No app-global
state, second installer, actual listener or host-routing rewrite is introduced.

The private health adapter serves the Core GET template and admits only exact
raw liveness/readiness paths, empty query/body and a single bounded Bearer.
It reuses the existing header/query framing and rejects the first nonempty body
chunk, without collecting a body. Shared header/path/query and individual body
chunk limits remain bounded; elapsed streaming time and empty-chunk count are
host concerns. Unknown kinds, aliases and malformed requests invoke no callback.
Router-generated HEAD rejection/redirect/unmatched responses likewise do not
invoke health code and are not semantic results; ordinary routing is unchanged.

One threadpool call encloses synchronous admission, callback and result
construction. It is not a callback timeout/cancellation mechanism. All four
nominal outcomes use HTTP200 with exact Core canonical correlated bytes and
no-store. Adapter-generated framing/auth/kind/internal failures use fixed bounded
400/413/401/404/500 bodies with no-store, never callback diagnostics or a fabricated
semantic outcome. Static status continues to describe variable-registry coverage,
not health, and its distinct signed authority remains required.

Security/history: supplied local configuration and callback code are trusted.
The SDK owns no graph/attempt approval, key custody, signing service, durable
truth/history, transaction or provider authority. No raw credential/context is
passed into callbacks or returned in errors. There is no health cache/replay
ledger: repeated valid reads retain the request observation identity even if
invoked again. Operations owns fresh observations, retries and durable records.
Zero protected callbacks is the SDK denial law, not gateway zero-network proof.

Owning tests use real signed generated test credentials through the actual
verifier and ASGI installer, callback counters, Core result bytes, negative
framing/locality/time, closed outcomes/error redaction, per-app separation,
single-publication collisions, retained mixed variable replay and off-loop
execution. Existing legacy/installed laws stay intact; only the additive public
signature and narrow new adapter import-owner inventories change. The normal
pinned Docker-backed test.sh is the authoritative gate, with no substitute
harness or compulsory failing-suite ceremony.

Handoff: SDK #21 consumes this neutral dispatcher for standard-library/shared
host composition, listener lifetime and application-response preservation.
Product owners must reuse actual workload health functions and retain existing
health endpoints. Native supervision and product/provider/image/live acceptance
remain separately gated, with Python product adoption first. Touched companions
overlap pending documentation PR19 and must retain current-source truth on merge.
