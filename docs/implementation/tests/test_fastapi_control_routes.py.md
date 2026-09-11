Source: [tests/test_fastapi_control_routes.py](../../../tests/test_fastapi_control_routes.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

These unittest cases install the complete optional route family into actual
local FastAPI apps and send test ASGI requests with generated signed credentials,
recording variables and controlled clocks/thread gates. They exercise the
application adapter without a network listener, TLS, provider or durable store.

Installation assertions compare the four routes with pinned Core data, keep
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

This companion used the full three route/installer source owners and selected
substantive assertions from this large test file, with actual Core 0ee72c3
route/result contracts. It is not a full fixture-permutation or transitive
framework audit. See [installer](../src/control_plane_kit_server_sdk/fastapi.py.md)
and [surface adapter](../src/control_plane_kit_server_sdk/_fastapi_surface_routes.py.md).
Executable validation belongs to the Docker-backed package gate.
