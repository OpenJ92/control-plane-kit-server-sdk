# Decision 0006: Structural Control-Plane Variable Protocol

Status: Accepted for the variable protocol boundary.

## Decision

`ControlPlaneVariable` is the SDK's one public extension model. It is a
runtime-checkable structural protocol with exactly three semantic members:
`descriptor`, `read`, and `apply`. Implementations do not inherit an SDK base
class. The descriptor, command request, read results, and transition results
are the exact existing core types; the SDK publishes no aliases that become a
second wire or result language.

Read and transition result parameters are covariant. The command parameter is
contravariant and bounded to `NodeControlCommandRequest`. The read bound admits
only read success, rejection, or failure. The transition bound admits only
transition success, rejection, or failure. Exact core result codecs provide
executable operation and descriptor compatibility.

The accepted apply signature retains both command and context for command
contravariance, with one mandatory request-source law:
`command is context.request`. Equality is insufficient because the exact
context object is what crossed the outer boundary. Every implementation checks
identity before domain work. Mismatch returns an apply-operation
`NodeControlRejected` with `INVALID_COMMAND`, using only the context request
identity, and changes no state, revision, ledger, or transaction. Candidate
material and repr are never rendered.

Runtime protocol checks prove member presence only. They do not prove method
signatures, annotations, variance, return values, authentication, graph
membership, admission, or provenance. Static checkers consume the inline
annotations; exact core codecs execute returned-result compatibility.

The package explicitly installs an empty package-local `py.typed` marker. The
marker makes the inline annotations discoverable under PEP 561 but does not
turn runtime membership into static proof. No type checker or framework is a
base runtime dependency.

## Ownership

The independent durable example is a test-owned service and UnitOfWork adapter.
It owns its own state, revision, ledger, transaction, idempotency, and replay
semantics and conforms without SDK inheritance. The SDK protocol owns no
holder, storage, lock, registry, UnitOfWork, ledger, or persistence behavior.

Issue #1481 implements the process-local atomic variable against this same
protocol. It preserves the exact request identity law. Its state and version
do not survive process restart; it owns no replay guarantee.

## Security And Operations

The protocol adds no authentication, authority, graph lookup, network route,
listener, transport, provider effect, durable mutation, or operational history.
The identity precondition prevents competing local request sources but does not
prove that an outer verifier or admitted-graph join ran. Closed mismatch
evidence and representation-free rejection keep candidate request, endpoint,
provider, exception, and secret material out of routine diagnostics.

## Consequences

Process-local and durable workload owners can share one typed structural
surface while retaining their proper state and transaction boundaries.
Runtime, static, codec, and packaging evidence remain separate and honestly
named. A new handler, plugin, reflection validator, or persistence abstraction
would require a separate public decision rather than extending this protocol.
