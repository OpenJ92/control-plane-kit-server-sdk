Source: [src/control_plane_kit_server_sdk/_replay.py](../../../../src/control_plane_kit_server_sdk/_replay.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This private synchronous coordinator receives an already admitted exact APPLY
request, its exact Core result codec and a dispatch callback. It does not
authenticate credentials. One coordinator's idempotency keys are global within
that instance: matching key/digest callers share one dispatch; changed request
intent conflicts, even across variables or targets. Different coordinators are
independent. Trusted route composition must choose the intended application scope.

A condition lock protects reservations and publication, while dispatch runs
outside the lock. In-flight entries count against capacity, never expire and
are not evicted. Same-thread reentry fails rather than deadlocking; other callers
wait without a timeout. Unrelated keys can progress if capacity remains. Default
capacity is 1,024, with an exact integer maximum of 4,096. A stuck owner can hold
its reservation indefinitely; this is not a liveness or distributed coordination
mechanism.

Terminal results are exact APPLY success/rejection/failure values, normalized
through the selected Core result codec into compact UTF-8 JSON capped at 16 KiB.
Each return decodes a fresh copy and checks the request ID. The input request
digest and those bounds come from the consumer's Core 0ee72c3 contracts, not
latest upstream. No callback-owned object is retained as the replay result.

Ordinary dispatch/normalization failure publishes a request-keyed NodeControlFailed.
An invalid completion-clock sample also publishes that failure but makes the
entry unprunable. Process-control BaseExceptions caught from dispatch, result
normalization or completion-clock sampling are re-raised only after publishing
failure and waking waiters; they likewise prevent pruning. Other instructions
and lock acquisition are not covered by a universal cancellation guarantee.
This does not undo any workload side effect that already occurred. The trusted
callback owns its transaction and durable truth.

For valid completion, the first subsequent pruning observation anchors retention
at the greater of its time and the completion sample. The entry then retains
300 seconds, the selected Core maximum grant lifetime; it cannot age out before
publication or during a long idle period before that first observation. Pruning
happens on later execute calls, not a background worker. Invalid initial clocks
or call shapes create no reservation. Failed entries that cannot safely age out
may consume capacity for the remaining lifetime of the coordinator.

Fixed private error categories omit request/key/result details. Raw process-control
exceptions are still re-raised to their caller. There is no persisted ledger,
cross-process lock, restart reconstruction, provider effect or grant issuance.
See [replay tests](../../tests/test_process_local_replay.py.md) and
[decision 0011](../../../../docs/decisions/0011-process-local-node-control-replay.md).
Synchronous verification/replay/workload interpretation must run off the ASGI
event loop in the owning adapter.
