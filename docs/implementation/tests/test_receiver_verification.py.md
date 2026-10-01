Source: [tests/test_receiver_verification.py](../../../tests/test_receiver_verification.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

Four SDK43 targets cover L4–L11: signed health profile/trust refusals before callbacks, declared local command/surface successor results, exact receiver invocation-context retention, and correlated process-local APPLY replay with changed-context conflict. Ephemeral signed fixtures and Core request/result roundtrips precede SDK boundaries. Existing interpreter entrypoints and argument names are used at the initial checkpoint, avoiding absent-keyword red.

The existing wrapper, invocation context and replay type refusal are the intended initial missing behaviors. Later assertions are not credited until reached; ordinary old tests remain unchanged and collectable at this checkpoint. Receiver digest correlation does not prove authentication or execution on its own. Replay remains process-local, not durable exactly-once or a controller dispatch/history service. All owning execution remains in the unchanged Docker suite.

The implementation candidate adds variable-only wrapper coverage, authenticated
retry before replay, changed-context conflict, and Python-equal bool/number
requests with different canonical digests. A wrong request-bound codec reserves
nothing; a wrong correlated terminal becomes one bounded failure without
redispatch. A signed foreign receiver with inconsistent redundant command claims
must remain401, while its fully bound counterpart is403; subsequent legitimate
local execution proves denial did not reserve the key. Existing translated
route tests cover all four outcomes. Target-red evidence credits only the
reached old setup/type refusals, not these later assertions; candidate evidence
must come from the unchanged owning gate at the final commit.
