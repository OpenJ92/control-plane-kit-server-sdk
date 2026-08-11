# control-plane-kit-server-sdk

Framework-neutral workload node-control SDK for Control Plane Kit.

This repository is the separately installable workload-facing SDK boundary
defined by
[control-plane-kit ADR 0010](https://github.com/OpenJ92/control-plane-kit/blob/develop/docs/adr/0010-node-control-route-prefix-and-server-sdk.md).
It consumes the pure node-control contracts published by
`control-plane-kit-core`; core will never import this repository.

The source distribution is installable from a checkout:

```bash
python -m pip install .
```

It is not published to a package index. The base dependency is the immutable
`control-plane-kit-core` source at
`0ee72c3fcdfbee5094357152bdf070fbfc53393c`; installing from a clean checkout
resolves that archive pin without requiring git.

Signature-verification dependencies are isolated in one exact optional extra:

```bash
python -m pip install ".[verification]"
```

That extra contains only `PyJWT==2.13.0` and `cryptography==50.0.0`. The base
install and root import remain free of both modules. This establishes bounded
dependency availability only; #1498 owns the closed signed-grant verifier.
These exact pins constrain the two named direct dependencies only.
They do not lock transitive dependency versions, artifact hashes, or publisher attestations.

FastAPI applications may install the public optional adapter dependency set with:

```bash
python -m pip install ".[fastapi]"
```

That extra contains the same verification pair plus `fastapi==0.141.1` and
`starlette==1.6.0`. It supports the one public, optional FastAPI composition:

```python
from control_plane_kit_server_sdk.fastapi import install_cpk_control_routes

install_cpk_control_routes(
    app,
    target=target,
    declaration=declaration,
    variables=variables,
    command_verifier=command_verifier,
    surface_read_verifier=surface_read_verifier,
)
```

The installer validates and constructs the complete four-route CPK surface
before replacing the host route list once. The SDK root remains lazy and
framework-neutral.
Authenticated APPLY invokes the caller-supplied variable and can mutate
process-local or durable workload-owned state. The SDK adapter owns no storage,
transaction, graph authority, or provider client; #1506 replay remains its
accepted cancellation, retry, and convergence boundary.

The root import exposes one neutral invocation value:

```python
from control_plane_kit_server_sdk import ControlPlaneInvocationContext, __version__

context = ControlPlaneInvocationContext(request)
assert context.request is request
assert __version__ == "0.1.0"
```

`ControlPlaneInvocationContext` retains the exact core request supplied by an
outer adapter. It does not authenticate the request. It does not prove graph membership.
It does not prove admission or provenance. The value is frozen and slotted, and
its request is excluded from its representation. Protocol interpretation,
state, verification, replay, route, and framework behavior remain assigned to
their named later issues.

`ControlPlaneVariable` is the one structural extension for process-local and
durable workload-owned variables. It declares `descriptor`, `read`, and `apply`
over the existing core descriptor, command, and disjoint result variants. An
apply implementation must check `command is context.request` before domain
work; a mismatch returns context-keyed closed invalid-command evidence without
rendering the candidate.

The runtime-checkable protocol proves member presence only. Static checkers own
signature and variance analysis, and exact core codecs execute returned-result
compatibility. The installed package includes an explicit empty `py.typed`
marker for its inline annotations. The durable conformance example remains a
test-owned service and UnitOfWork; the SDK owns no storage or transaction.

`AtomicControlPlaneVariable` is the small process-local implementation for
workloads that need one in-memory state cell:

```python
from control_plane_kit_server_sdk import AtomicControlPlaneVariable

variable = AtomicControlPlaneVariable(descriptor, initial_state)
```

It preserves `command is context.request`, checks the expected version, and
publishes a whole immutable state snapshot atomically. It captures a snapshot
under its lock; apply must compare outside the lock, then
identity-revalidates the snapshot under the lock before publication. A changed
state advances one version; equal state returns no-change; a changed state at
the max-safe version fails without publication. It is process-local: state and
version do not survive restart. Issue #1150 owns replay, cache, ledger, and
idempotency-key interpretation.

`WorkloadNodeControlVerifierKeySet` carries one bounded, deterministic snapshot
of exact core public verification material for workload-node-control grants.
`AtomicWorkloadNodeControlVerifierKeySet` publishes a whole supplied snapshot
for process-local readers:

```python
from control_plane_kit_server_sdk import (
    AtomicWorkloadNodeControlVerifierKeySet,
    WorkloadNodeControlVerifierKeySet,
)

key_set = WorkloadNodeControlVerifierKeySet(purpose, public_keys)
verifier_keys = AtomicWorkloadNodeControlVerifierKeySet(key_set)
assert verifier_keys.snapshot() is key_set
```

Public PEM is non-secret but integrity-sensitive and is omitted from routine
representations. The key set does not prove producer provenance, graph
admission, lifecycle status, or authority. Trusted composition must supply a
complete snapshot after every process restart. Expected issuer and audience
are trusted process-composition inputs to the #1498 verifier; #1150 owns
authenticated route accrual, replay, cache, ledger, and idempotency-key
interpretation.

Consumers of `.[verification]` may import the optional closed verifier directly:

```python
from control_plane_kit_server_sdk.verification import (
    Ed25519WorkloadNodeControlVerifier,
)

verifier = Ed25519WorkloadNodeControlVerifier(
    verifier_keys,
    expected_issuer="cpk-server",
    expected_audience="workload:router:control",
    clock=trusted_clock,
)
request = verifier.admit(
    credential,
    route_operation=operation,
    route_variable=variable,
    candidate=candidate,
)
```

The compact type is exactly `CPK-WORKLOAD-NODE-CONTROL+JWT`. Admission uses
one trusted clock and exact `PyJWT==2.13.0` plus `cryptography==50.0.0` direct
dependencies. Canonical compact framing and duplicate-aware bounded JSON are
checked before maintained Ed25519 admission; authentication precedes candidate
decoding. The verifier returns only an exact core request and never retains or
renders the credential, signature, or candidate. It intentionally retains the
process-local public-key holder and reads its non-secret, integrity-sensitive
public material during admission; that holder and material remain absent from
routine representations and diagnostics. It owns no private key, route
framework, graph admission, mutation, or durable state.

Replay remains deliberately outside this verifier. Issue #1150 owns replay,
cache, ledger, idempotency-key interpretation, and authenticated route accrual.

The first #1150 child, #1506, adds a private process-local replay coordinator
for already admitted APPLY requests. It stores at most 16,384 result bytes per
entry, retains published terminals for exactly 300 seconds, and never prunes an
in-flight reservation. It is not durable: restart loses all entries, while
domain-owned durable variables retain their own ledger and transaction truth.

The coordinator is synchronous. The private #1551 FastAPI interpreter receives
one coordinator per application or route set, preserves admission and exact
target binding before replay, and runs interpretation through one worker-thread
handoff rather than blocking an event loop. It adds no public SDK export,
authentication claim, graph authority, provider effect, or persistence boundary.

Surface-read authority uses a separate process-local public verification
material lane. `WorkloadNodeControlSurfaceReadVerifierKeySet` accepts only the
`WORKLOAD_NODE_CONTROL_SURFACE_READ` purpose, and its atomic holder never
substitutes for the command holder. Consumers import the optional verifier
directly:

```python
from control_plane_kit_server_sdk.verification import (
    Ed25519WorkloadNodeControlSurfaceReadVerifier,
)

request = verifier.admit(
    credential,
    route_kind=kind,
    candidate=None,
)
```

The compact type is exactly
`CPK-WORKLOAD-NODE-CONTROL-SURFACE-READ+JWT`, and its signed payload member is
`workload_node_control_surface_read`. Credentials are bounded to 4,096 bytes;
the protected header, payload, and signature segments are bounded to 512,
3,840, and 128 bytes. Admission returns one exact core surface-read request.
It is stateless: the same valid credential may be admitted again during its
bounded lifetime. The verifier owns no private key, no HTTP framing, no
registry lookup, no registry state, no result construction, and no replay
store. The #1507 FastAPI adapter owns HTTP extraction, the installed-variable
snapshot, and execution of the admitted read. It bounds route/body inputs and
proves bodylessness before calling admission; successful admission precedes
local declaration/registry access and result production.

## Validation

Run the authoritative Docker-first package gate with:

```bash
./test.sh
```

The default gate is pinned package evidence. Before package build or dependency
resolution, a structured TOML preflight requires `project.dependencies` to be
the exact one-element immutable core coordinate and
`project.optional-dependencies` to be the exact `verification` and `fastapi`
map declared in `pyproject.toml`. The gate then checks package integrity and
builds once. A base container proves the SDK without optional dependencies; a
verification container proves `.[verification]`; and a FastAPI container
installs `.[fastapi]`, runs the complete suite, and proves exact installed
versions plus SDK-root import laziness. All containers and the image have
process-scoped names and cleanup.

Coordinated source development may explicitly replace only the core dependency:

```bash
CPK_SERVER_SDK_DEPENDENCY_MODE=local-core \
CPK_CORE_REPO=/absolute/path/to/control-plane-kit \
./test.sh
```

Local-core mode is composition evidence; it is not the default package or CI proof.
It retains the same metadata preflight before substituting the explicit read-only
checkout. Merely having a sibling checkout does not change what is tested.

The repository does not own control-plane operations stores, cpk-server,
Docker interpreters, server products, provider clients, or application state.
FastAPI support is an optional public submodule rather than a base or package-
root dependency; the root import remains framework-neutral.
