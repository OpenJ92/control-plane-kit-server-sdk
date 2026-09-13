Source: [src/control_plane_kit_server_sdk/atomic.py](../../../../src/control_plane_kit_server_sdk/atomic.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This concrete variable owns one process-local state/version snapshot and lock.
It retains exact Core descriptor/state values, checking state-codec agreement
and a nonnegative version bounded by the maximum safe JSON integer. It does
not clone/revalidate every nested Core field or authenticate the context.

Apply checks command identity against context.request before dispatch and
precondition checks. It captures a snapshot under the lock, compares candidate
state outside the lock, prepares the result, then rechecks snapshot identity
under the lock before publication. Caller-defined equality can run through
Core-admitted nested text; holding the lock during that comparison would block
readers. Equality failures return a closed failure.

Unchanged state preserves the version; changed state increments once.
A competing publication rejects the stale operation, including a would-be
no-change. At the version limit, changed state fails without publication.
The [atomic decision](../../../../docs/decisions/0007-atomic-control-plane-variable.md)
records this concurrency design.

State/version vanish on process restart. This owner provides no store, durable
history, replay guarantee, idempotency ledger or provider authority. Read/apply
results are existing Core values; outer adapters own authentication and target
admission. The [tests](../../tests/test_atomic_variable.py.md) exercise local
thread interleavings, not distributed concurrency or database isolation.
