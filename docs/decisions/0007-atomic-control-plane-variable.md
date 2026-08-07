# Decision 0007: Atomic Control-Plane Variable

Status: Accepted for the process-local atomic implementation.

## Decision

`AtomicControlPlaneVariable` is one concrete, slotted implementation of the
existing `ControlPlaneVariable` protocol. Its constructor accepts an exact
`ControlPlaneVariableDescriptor`, an exact scalar, map, or weighted-routing
core state whose kind matches that descriptor, and an optional bounded initial
version. It retains the descriptor and state by identity.

Read captures one immutable state/version snapshot under a private lock and
constructs the read result after releasing the lock. Apply preserves the sole
request source law, `command is context.request`, then checks operation,
variable, codec, state kind, and expected version before candidate comparison.

Core-admitted nested public text may be a `str` subclass whose equality invokes
caller behavior. Apply therefore captures under the lock, performs candidate
compare outside the lock, prepares the complete result and next snapshot, and
then identity-revalidates the captured snapshot under the lock. Only that final
critical section may publish the new snapshot. A concurrent publication makes
the earlier apply fail its precondition, including an otherwise equal-state
no-change. Equality exceptions become a closed apply failure without rendering
exception or candidate material.

Equal state returns no-change at the captured version. Changed state publishes
one new snapshot at version plus one. Changed state at the max-safe version
returns failure and publishes nothing.

## Ownership

This object is process-local. State and version do not survive process restart.
It has no store, UnitOfWork, transaction, callback, retry loop, or durable
history. Issue #1150 owns replay, cache, ledger, and idempotency-key
interpretation. The outer adapter owns authentication, graph admission,
provenance, target dispatch, and end-to-end grant verification.

## Security And Concurrency

Request-source mismatch and malformed dispatch use closed invalid-command
evidence. Stale snapshots use closed precondition evidence. Equality failure
uses closed internal-failure evidence. Candidate state, exception text,
requests, endpoints, provider diagnostics, and secret material are never
rendered in those outcomes.

No candidate comparison or result construction occurs while the lock is held.
Readers can capture the current snapshot while another apply is blocked in
caller equality. Snapshot identity, rather than value equality, closes the
revalidation step and prevents an ABA publication.

## Consequences

The SDK offers a minimal in-memory reference implementation without creating a
second validator, result language, persistence abstraction, replay policy, or
authority marker. Durable workload owners continue to implement the structural
protocol over their own transaction boundaries.
