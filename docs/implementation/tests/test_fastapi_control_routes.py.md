Source: [tests/test_fastapi_control_routes.py](../../../tests/test_fastapi_control_routes.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

Existing legacy FastAPI tests remain behavioral compatibility evidence: exact four-route publication, app/collision/state preservation, read/apply/replay, static declaration/registry coverage, auth before locality/disclosure and off-loop work. SDK23 changes only the public signature inventory for optional health_dispatcher, default empty variables and optional command-verifier typing. V1 runtime semantics still require the command verifier, with its original validation precedence.

No old behavioral assertion is weakened. Dedicated new tests cover health-only/mixed installation and real signed health ASGI effects. These in-process framework tests are distinct from installed dependency probes, actual listeners or provider/live acceptance.

## Behavior and evidence details

These unittest cases install the complete optional route family into actual
local FastAPI apps and send test ASGI requests with generated signed credentials,
recording variables and controlled clocks/thread gates. They exercise the
application adapter without a network listener, TLS, provider or durable store.

Installation assertions compare the legacy four routes with pinned Core data, keep
existing route/state/OpenAPI identities intact, and require failure before host
mutation. Collision cases cover root/control mounts, Host, parameterized first
segments, subclasses/unknown types and disjoint ordinary routes. Partial marked
installation remains installed; removing all marks permits a fresh pre-startup
install. First ASGI execution closes the installation window. Two apps keep
distinct route/registry/replay state.

Behavioral cases cover exact Core read/apply results, one-dispatch replay with a
waiting caller while the event loop progresses, canonical stateless capability
and registry-status projections, and empty/partial/complete coverage. Framing
must reject before admission/discovery; authenticated foreign target/declaration
must reject before disclosure. Recorded clock thread IDs verify off-loop work
for the selected calls. These schedules and fixtures do not establish all
concurrency behavior, cryptographic dependency correctness or runtime health.
