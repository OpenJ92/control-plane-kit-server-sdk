Source: [tests/test_atomic_variable.py](../../../tests/test_atomic_variable.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This file protects constructor admission, read/apply dispatch, version
preconditions, no-change versus changed-state results and version exhaustion.
Controlled thread/event witnesses block caller equality outside the lock, allow
another writer to publish, then require the stale candidate to reject, even if
its compared state was equal.

Candidate identity and stale-precondition cases must not reach state equality.
Equality failures preserve the snapshot and use closed evidence. These are
process-local concurrency laws, not restart recovery, durable replay or
distributed consistency. Source-shape assertions supplement behavioral tests;
they are not a substitute for the interleaving witnesses.
[atomic.py](../src/control_plane_kit_server_sdk/atomic.py.md) owns the algorithm.
