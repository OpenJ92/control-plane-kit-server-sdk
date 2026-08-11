# Decision 0014: Atomic FastAPI Control Route Installation

Status: Accepted

Issue #1552 completes #1507 by composing the private variable-route
interpreter from #1551 with authenticated, stateless capability and status
reads. The public optional module exports one operation:

```python
install_cpk_control_routes(
    app,
    target,
    declaration,
    variables,
    command_verifier,
    surface_read_verifier,
)
```

The package root remains framework-neutral and does not export this function.

## Chosen Shape

Installation constructs one immutable variable registry and one application-
local replay coordinator. The registry feeds both interpreter families:

```text
declaration + live variables
  -> one descriptor snapshot and result codec per installed variable
    -> capability/status projection
    -> READ/APPLY interpretation and replay
```

All validation, collision classification, route construction, canonical-route
verification, and private route marking happen away from the host application.
The one successful host mutation is:

```python
app.router.routes = [*prior_routes, *cpk_routes]
```

The installed route family is exactly the core `NODE_CONTROL_ROUTES` value and
is excluded from generated OpenAPI documents. Installation is allowed only
before FastAPI constructs its middleware stack.

## Composition Laws

- Existing exact FastAPI and Starlette route types compose only when their
  first literal path segment is disjoint from `__control`.
- Parameterized first segments, root/control mounts, host dispatch, subclasses,
  and unknown route types fail closed.
- Any retained marked CPK route reports an existing installation. Removing all
  four marked routes is an explicit uninstall and permits a fresh install.
- Existing route identities and state remain unchanged on success and failure.
- Two applications receive distinct registries, routes, targets, and replay
  coordinators.

## Security And Effects

Transport bounds and credential admission precede target binding or surface
disclosure. Surface grants must bind the exact target and declaration identity.
Errors are closed, bounded, and do not include credentials, candidates,
provider exceptions, or graph addresses. Synchronous verification, result
construction, replay waits, and workload invocation run outside the event loop.

Capability and status reads are pure projections over the declaration and the
installed registry snapshot. READ calls workload-owned code. APPLY may mutate
workload-owned state and remains governed by the accepted process-local replay
algebra. The installer adds no persistence, transaction, graph authority,
provider client, or application lifecycle behavior.

## Dependency Boundary

The `fastapi` extra pins exactly `PyJWT==2.13.0`, `cryptography==50.0.0`,
`fastapi==0.141.1`, and `starlette==1.6.0`. Directly pinning Starlette makes the
closed route classifier an explicit tested dependency rather than an implicit
transitive assumption.

## Alternatives Rejected

- Four incremental `add_api_route` mutations were rejected because a later
  failure could leave a partial control surface.
- Application state or a module-global installation registry was rejected
  because it would add hidden host mutation or cross-application coupling.
- Name-prefix deletion or collision inference was rejected because ownership
  and compatibility must be established from exact route types and markers.
- Public partial installers were rejected because products should have one
  preferred way to install the complete CPK control surface.
