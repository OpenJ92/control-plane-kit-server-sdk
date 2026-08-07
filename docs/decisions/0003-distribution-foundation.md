# Decision 0003: Distribution Foundation

Status: Accepted for the distribution foundation.

## Decision

The separately installable distribution is named
`control-plane-kit-server-sdk`. Its Python import package is
`control_plane_kit_server_sdk`, its initial version is `0.1.0`, and it supports
Python 3.11 and later.

The base dependency list contains exactly `control-plane-kit-core` from the
immutable accepted source coordinate
`OpenJ92/control-plane-kit@3d85dc76300bf88be923531445ce83e9b6c7b23e`.
The dependency uses the GitHub archive and `control-plane-kit-core`
subdirectory so a clean Python image does not need a git client. The full Git
SHA identifies source; it is not a signed wheel or package-publication proof.

The package root exports only `__version__`. It performs no eager core import
and loads no framework, operations, database, provider, product, cryptography,
or server-process package.

## Deferred Ownership

No runtime, protocol, request context, state holder, key set, grant verifier,
route, replay cache, listener, provider effect, image, or application mutation
is introduced here. Issue #1480 owns the first typed public SDK protocol.

No package publication is performed or implied. The distribution is installed
from a checkout for current source validation.

Issue #1485 owns the canonical Dockerfile, `test.sh`, package-integrity policy,
pinned/local dependency modes, and attached CI. This issue uses direct Docker
commands only and does not create a temporary gate.

## Consequences

Later SDK behavior has one stable distribution/import identity and one-way core
dependency. Root behavior remains intentionally empty until its owning child
adds and tests a public API. A `py.typed` marker is deferred until typed public
contracts exist.
