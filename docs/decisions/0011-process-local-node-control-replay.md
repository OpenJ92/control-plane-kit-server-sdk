# Decision 0011: Process-Local Node-Control Replay

Status: Accepted

Issue: #1506

## Decision

The SDK owns one private, synchronous process-local coordinator for replay of
already admitted node-control APPLY requests. It uses the exact request
`idempotency_key` as app-local identity and the core canonical request digest
as intent identity. Same-key/same-digest callers converge on one dispatch and
fresh strict result copies; changed intent conflicts before dispatch.

In-flight reservations are capacity-counted, non-expiring, and non-prunable.
Terminal retention begins at publication and lasts exactly 300 seconds. The
coordinator stores compact UTF-8 JSON result bytes capped at 16,384 bytes per
entry. At most 4,096 entries may exist. Unexpired or in-flight entries are not
evicted to admit unrelated work.

The coordinator is not durable. Restart loses all entries, and it creates no
ledger, transaction, provider effect, or cross-process coordination. Durable
workload variables retain their own replay and transaction truth.

## Failure And Security Boundary

Invalid calls, conflicts, capacity exhaustion, and same-owner re-entry use
fixed private material-free categories. Once an owner reserves a key, dispatch,
result-normalization, or completion-clock uncertainty publishes a bounded
request-keyed core failure before waiters wake. Process-control exceptions are
re-raised only after that publication. Request, key, digest, result, exception,
credential, public material, endpoint, and provider values are absent from
routine diagnostics.

The coordinator receives one exact plain request at a trusted internal seam.
It does not authenticate credentials or establish authority. The accepted
signed verifier remains responsible for admission before replay. Graph
membership, grant issuance, capability/status language, provider mutation, and
route authorization remain outside this module.

## Route Handoff

Issue #1507 must install one coordinator per FastAPI application or route set.
Because `execute` is synchronous and may block on a condition, the complete
route call must run on a worker thread through a synchronous endpoint or one
explicit threadpool boundary. It must never block the event-loop thread.

#1507 must prove admission before replay, app-global key scope, same-key
convergence and conflict, and isolation between two application instances. It
must not add an authority marker to the invocation context.

## Alternatives Rejected

- A public replay protocol would add a second workload extension model.
- Lock-held dispatch would serialize unrelated work and execute caller code
  inside replay state protection.
- FIFO eviction would permit live replay authority to disappear under load.
- Persistent replay belongs to domain-owned durable variable implementations,
  not this framework-neutral SDK helper.
