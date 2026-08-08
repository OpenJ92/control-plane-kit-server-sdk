# Decision 0009: Verification Dependency Proof

Status: Accepted for dependency availability.

## Decision

The base SDK keeps its exact immutable `control-plane-kit-core` coordinate and
adds one optional extra, `.[verification]`. Its complete dependency list is
exactly `PyJWT==2.13.0` followed by `cryptography==50.0.0`; no other optional
extra is accepted.

The structured TOML preflight compares both the base dependency list and the
complete optional-dependency map before package build or dependency resolution.
Failure is one bounded category and never echoes candidate coordinates or
metadata.

The authoritative gate builds one image, then uses distinct process-scoped
containers. The base phase installs and imports the SDK without optional
dependencies. The verification phase installs `.[verification]`, compiles and
runs the package tests, imports the SDK root before either optional module, and
checks both installed distribution versions before importing `jwt` and
`cryptography`. Cleanup removes only the two exact containers and image owned
by the current shell process.

## Boundary

This decision proves dependency availability. **No verifier behavior** is
introduced: there is no token parsing, signature verification, algorithm or
claim policy, issuer/audience decision, credential admission, replay, route,
framework adapter, network listener, durable state, or provider effect. Issue
#1498 owns the closed signed-grant verifier and must consume the already
accepted process-local public-key snapshot without expanding this package
proof into authority.

The SDK source package does not import `jwt` or `cryptography`; only the
installed gate probe imports them after proving that the root import was lazy.
Errors are bounded and categorical and do not render versions, paths, module
state, exception text, credentials, compact grants, signatures, or public-key
material.

## Consequences

Base consumers do not receive cryptographic dependencies. Verification
consumers opt into one reviewable, reproducible dependency pair, while the
later verifier remains responsible for all cryptographic and authorization
semantics.
