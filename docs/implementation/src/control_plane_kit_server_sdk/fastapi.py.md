Source: [src/control_plane_kit_server_sdk/fastapi.py](../../../../src/control_plane_kit_server_sdk/fastapi.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The optional public installer composes exactly four Core node-control routes:
capabilities, status, variable READ and variable APPLY. It requires exact FastAPI,
router, target, declaration and verifier types and a tuple of live variables,
before the app has built its middleware stack. The package root stays neutral;
importing this optional module brings framework and verification dependencies.

Preparation checks existing routes before taking the variable descriptor snapshot,
constructs one private registry and replay coordinator, builds both route families,
compares their ordered names/methods/paths to consumer Core 0ee72c3 NODE_CONTROL_ROUTES,
and marks the new routes privately. Only successful preparation replaces the host
route list once, preserving prior route object identities. No app-state flag or
global installation registry is used. This is serialized startup composition,
not a lock/transaction against concurrent host route edits; trusted descriptor
callbacks remain caller-owned code.

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
