# control-plane-kit-server-sdk

Framework-neutral workload node-control SDK for Control Plane Kit.

This repository is the separately installable workload-facing SDK boundary
defined by
[control-plane-kit ADR 0010](https://github.com/OpenJ92/control-plane-kit/blob/develop/docs/adr/0010-node-control-route-prefix-and-server-sdk.md).
It will consume the pure node-control contracts published by
`control-plane-kit-core`; core will never import this repository.

Repository genesis intentionally contains no Python package or runtime
implementation. Issue
[OpenJ92/control-plane-kit#1479](https://github.com/OpenJ92/control-plane-kit/issues/1479)
owns the distribution metadata, package policy, Docker-first test gate, and
lightweight import surface.

The repository does not own control-plane operations stores, cpk-server,
Docker interpreters, server products, provider clients, or application state.
FastAPI support is a later optional adapter rather than a base dependency.
