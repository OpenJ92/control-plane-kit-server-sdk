# Decision 0001: Repository Foundation

Status: Accepted for repository genesis.

## Decision

`OpenJ92/control-plane-kit-server-sdk` is the public repository for the
separately installable `control-plane-kit-server-sdk` distribution. Its future
Python import package is `control_plane_kit_server_sdk`.

The default branch is `main`. Development integrates through `develop`, with
issue branches targeting `develop` before coherent promotion to `main`.

The SDK consumes a checksum-visible immutable coordinate of the
`control-plane-kit-core` distribution. The accepted source contract at genesis
is `OpenJ92/control-plane-kit@3d85dc76300bf88be923531445ce83e9b6c7b23e`.
Core never imports the SDK.

## Deferred Ownership

Issue OpenJ92/control-plane-kit#1479 owns repository agent policy, package
metadata, dependency declaration, installed import behavior, Docker-first
validation, and CI. Later issues own the public variable protocol, process-local
atomic state, verifier configuration, and optional FastAPI adapter.

Repository genesis adds no SDK source, tests, workflow, product, image, or
runtime behavior.
