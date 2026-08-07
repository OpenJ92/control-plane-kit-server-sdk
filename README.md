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

The repository does not own control-plane operations stores, cpk-server,
Docker interpreters, server products, provider clients, or application state.
FastAPI support is a later optional adapter rather than a base dependency.
