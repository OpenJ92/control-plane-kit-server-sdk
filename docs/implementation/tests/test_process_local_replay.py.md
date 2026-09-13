Source: [tests/test_process_local_replay.py](../../../tests/test_process_local_replay.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

These unittest cases exercise the private replay coordinator with exact Core
requests/results, injected dispatch functions, mutable clocks and controlled
thread/Event schedules. They require one dispatch for a matching key/digest and
fresh strict copies for both the owner and replay callers. Changed request ID,
target, variable or candidate under the same key conflicts before dispatch.

Concurrency cases keep in-flight reservations capacity-counted and unprunable,
allow an unrelated key to progress, and make same-thread reentry fail without
deadlock. Timing cases cover first post-publication anchoring, backward clocks
and lock-contended publication. Failure cases require bounded request-keyed
terminal failure after bad results, dispatch exceptions or completion-clock
uncertainty, with publication before process-control rethrow. Unprunable failure
continues to consume capacity. Separate coordinator instances each dispatch.

Serializer cases distinguish the compact UTF-8 byte bound from Python string
length and reject overflow/nonfinite JSON. Selected error/representation checks
exclude test secrets and idempotency material. The tests do not authenticate a
credential, prove all possible thread schedules, persist a ledger, restart a
process or roll back callback-owned data. Source/documentation assertions are
separate structural checks, not runtime evidence.

The original companion reviewed the full [replay owner](../src/control_plane_kit_server_sdk/_replay.py.md),
selected substantive test cases and then-selected Core 0ee72c3 result codec and
payload/lifetime constants. Current Core 95452249 adoption retained these tests;
the original review is not a fresh audit of every test helper or
transitive dependency. The repository's Docker-backed test.sh owns executable
validation; no new test run accompanies this documentation.
