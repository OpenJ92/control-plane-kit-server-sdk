# Decision 0005: Neutral Invocation Context

Status: Accepted for the invocation boundary.

## Decision

`ControlPlaneInvocationContext` is a frozen, slotted value with exactly one
representation-hidden field: the exact core `NodeControlCommandRequest`
received by a workload adapter. Construction accepts the core type itself for
both read-state and apply-command requests. Plain objects, structural
lookalikes, and subclasses are rejected with one categorical error that never
renders candidate material.

The context records what an outer adapter passed inward. It does not authenticate.
It does not prove graph membership, admission, or provenance. In particular, it
exposes no authority flag, grant, signature, key, header, wire codec, mutable
registry, replay store, or lock. Callers remain responsible for authentication,
graph-bound authorization, and provenance checks before constructing the value.

The package root exports the context and therefore imports the accepted pure
core request contract. Operations, interpreters, secrets, servers, frameworks,
provider clients, and persistence remain outside the package import boundary.

## Deferred Ownership

Issue #1487 owns the protocol and fake durable conformance surface. Because the
context already retains the exact request, that issue must either define and
check an identity law between a separately supplied command and
`context.request`, or choose a single request source. A mismatch rule may not
exist only as fake-fixture behavior.

State mutation, verification, replay, routes, framework adapters, provider
effects, and application persistence remain deferred to their named owners.

## Consequences

Workload adapters can carry one exact admitted request into later pure protocol
code without turning the context into evidence of trust. Structural tests keep
the value field-bounded and import-bounded, while exact representation and
error laws prevent request or rejected-candidate material from appearing in
ordinary diagnostics.
