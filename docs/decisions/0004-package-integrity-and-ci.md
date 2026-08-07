# Decision 0004: Package Integrity And CI

Status: Accepted for the package proof surface.

## Decision

The executable root `./test.sh` is the authoritative package gate. Its default
`pinned` mode installs the immutable core dependency declared by
`pyproject.toml` and is the only mode used by CI. An explicit `local-core` mode
requires `CPK_CORE_REPO` to identify a read-only Control Plane Kit checkout and
is labeled composition evidence, not pinned package evidence.

The gate runs the package-integrity policy before building the package image.
That policy counts discoverable standard-library unittest identities and fails
closed on hidden or placeholder tests, pytest, swallowed exceptions, mutable
legacy imports, stale or unapproved skips, and proof-changing gate options.
The approved-skip manifest starts empty.

The Dockerfile has package and test stages. The package stage installs the SDK
without dependencies; the gate then interprets the selected dependency mode,
compiles source and tests, runs every discoverable package test, and imports the
installed SDK from outside the source tree. Each invocation owns names derived
from its shell process and removes only its exact test container and image.

GitHub Actions invokes the same default `./test.sh` command for pull requests,
pushes to `develop` and `main`, and manual dispatch. Workflow permissions are
limited to `contents: read`; it has no package, image, identity-token, or
publication authority.

## Deferred Ownership

No package publication, signing, registry login, image publication, protocol,
runtime, route, replay, grant verification, secret handling, provider effect,
or application mutation is introduced. Issue #1480 owns the first typed SDK
protocol only after this proof surface is accepted.

## Consequences

Package evidence is reproducible from one checked-in command, while coordinated
source composition remains possible without being confused with immutable-pin
proof. The integrity policy and command-equivalent CI make hidden collection or
weaker workflow validation visible in review.
