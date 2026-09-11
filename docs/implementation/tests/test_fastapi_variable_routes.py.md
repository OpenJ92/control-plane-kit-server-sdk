Source: [tests/test_fastapi_variable_routes.py](../../../tests/test_fastapi_variable_routes.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This unittest owner exercises the private READ/APPLY route builder using real
local FastAPI/ASGI dispatch, generated signed credentials and recording workload
variables. The fixtures intentionally bypass the public installer's four-route
collision/startup composition, which has its own test owner.

Registry cases allow an empty or declared subset, snapshot descriptors once and
reject unknown/duplicate/bad-shaped variables. Request cases distinguish streamed
body/header/path byte bounds, nonempty queries, duplicate/malformed credentials
and READ bodylessness before application calls. Fragmented APPLY must reconstruct
the exact candidate, while invalid candidate admission must not reserve replay.
These byte tests do not prove a chunk-count or whole-request time limit.

Locality tests bind all trusted target coordinates before registry lookup, so a
foreign target with an otherwise valid same-audience credential cannot discover
missing variables or occupy a local replay key. Every replay attempt authenticates
again. Matching intent converges, changed intent conflicts, capacity is bounded
per coordinator, and controlled concurrent requests share one worker result
while the event loop progresses. Thread-ID assertions distinguish worker work
from the event-loop thread; AST checks separately protect the intended handoff.

Selected results and exceptions must produce the closed protocol/status behavior
without fixture secret/target text. Ordinary routes remain usable. These tests
do not prove provider authorization, distributed replay, durable transactions,
network TLS or all possible thread schedules. Navigation used selected test
assertions and the full [adapter](../src/control_plane_kit_server_sdk/_fastapi_variable_routes.py.md),
with the actual Core 0ee72c3 codec and prior verifier/replay context; not every
fixture permutation was audited. Docker-backed test.sh owns execution.
