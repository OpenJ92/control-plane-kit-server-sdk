Source: [src/control_plane_kit_server_sdk/fastapi.py](../../../../src/control_plane_kit_server_sdk/fastapi.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The optional public installer remains the one atomic publication boundary. It validates exact app/router/target/declaration/verifier types and startup timing, then classifies V1 or V2 composition. V1 preserves the four existing routes and required command/static verifiers. Health-only V2 requires static authority plus an exact health dispatcher, rejects command verifier/nonempty variables, and constructs no command replay. Mixed V2 retains existing variable behavior/replay plus health. V2 dispatcher target/declaration must equal the install context.

Configuration and closed collision checks precede variable descriptor callbacks. Registry snapshots, optional route-family construction, exact ordered Core route shape and private marking complete off-app before the sole route-list replacement. Existing route object identities, partial variable-registry laws, startup constraints, marks and collision classifier are preserved. This is serialized startup composition, not a transaction against arbitrary concurrent host edits.

Static routes remain separately authenticated registry/declaration projections, not health. The private health adapter performs framing and uses the neutral dispatcher off-loop. No second FastAPI installer, global registry, actual listener or ordinary-routing rewrite is added. Core remains95452249; exact direct framework versions are unchanged. Completed SDK21 adds the separate passive [stdlib installer](stdlib.py.md), reusing shared interpretation. Tests cover the additive signature and concrete legacy/health-only/mixed behavior; companion integration retains this source truth.

SDK #26 extracts pure configuration validation and preparation to `_control_dispatch`. Host checks/collisions precede descriptor preparation; static routes capture that value, variable routes consume its exact registry/replay, and health uses its retained dispatcher. Public signature, shape, errors and publication are unchanged.

## Behavior and evidence details

The collision classifier accepts only exact known FastAPI/Starlette HTTP,
WebSocket and Mount types with a disjoint literal first segment. A root ordinary
route is allowed, while a root mount, parameterized first segment, __control
prefix segment, Host, subclass or unknown route type fails closed. This logic
depends on the explicitly selected framework versions; names alone are not an
ownership proof. Any retained marked route prevents another install. Removing
all marked routes permits a fresh install only if the other preconditions and
collision checks still pass; it also creates fresh process-local replay state.

Routes are excluded from OpenAPI, not made unreachable. Runtime authentication,
trusted target binding and workload interpretation live in the
[variable](_fastapi_variable_routes.py.md) and
[surface](_fastapi_surface_routes.py.md) owners. The installer adds no listener,
TLS, persistence, provider client or workload transaction. Ordinary preparation
failures become one of three fixed cause-free messages; BaseExceptions and
external caller effects are not a rollback guarantee. See
[installer tests](../../tests/test_fastapi_control_routes.py.md) and
[decision 0014](../../../../docs/decisions/0014-atomic-fastapi-control-route-installation.md).
