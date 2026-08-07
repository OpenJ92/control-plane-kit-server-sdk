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
`3d85dc76300bf88be923531445ce83e9b6c7b23e`; installing from a clean checkout
resolves that archive pin without requiring git.

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
belong to the held signed-verifier predecessor; #1150 owns authenticated route
accrual, replay, cache, ledger, and idempotency-key interpretation.

## Validation

Run the authoritative Docker-first package gate with:

```bash
./test.sh
```

The default gate is pinned package evidence. Before package build or dependency
resolution, a structured TOML preflight requires `project.dependencies` to be
the exact one-element immutable core coordinate declared in `pyproject.toml`.
The gate then checks package integrity, compiles the current source and tests,
runs every discoverable standard-library unittest, and imports the installed
SDK from outside the source tree.

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
FastAPI support is a later optional adapter rather than a base dependency.
