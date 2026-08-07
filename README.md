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

The current root import is deliberately lightweight:

```python
import control_plane_kit_server_sdk

assert control_plane_kit_server_sdk.__version__ == "0.1.0"
```

Protocol, state, verification, replay, route, and framework behavior remain
assigned to their named later issues.

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
