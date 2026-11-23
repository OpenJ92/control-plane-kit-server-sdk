# Decision 0002: Repository Policy

Status: Accepted for repository policy.

The original decision below records the repository's founding policy.
[CPK #2119](https://github.com/OpenJ92/control-plane-kit/issues/2119) supersedes
its branch topology. [GIT-FLOW.md](../../GIT-FLOW.md) defines the current
main-target flow, and [AGENTS.md](../../AGENTS.md) defines when a change needs
focused target-red evidence.

## Decision

The SDK follows a tests-before-source, issue-scoped development loop over
`main`, `develop`, and `codex/<issue-id>-<slug>` branches. Every non-trivial
change begins with law cards and a source dry run, freezes focused target-red
evidence, implements the smallest coherent concept, validates the exact head,
receives skeptical review, and leaves a decision log and dependent handoff.

Validation is Docker-first and uses standard-library `unittest`. Repository
security and exact resource ownership are reviewed in every loop. Broad Docker
cleanup and secret-bearing repository artifacts are forbidden.

The SDK consumes immutable pure core contracts one-way. It does not own
operations, products, provider effects, application truth, or cpk-server. Its
later public extension surface remains one `ControlPlaneVariable` model rather
than a generic handler or plugin system.

## Deferred Ownership

No package metadata or Python package is introduced here. Issue #1484 owns the
distribution identity, lightweight root import, and immutable core dependency.

No runtime, canonical package gate, Dockerfile, package-integrity framework, or
workflow is introduced here. Issue #1485 owns Docker-first package validation
and attached CI after #1484 is accepted.

Protocol, state, verification, replay, routes, framework adapters, images, and
publication remain with their named later issues.

## Consequences

Policy tests can become ordinary inputs to the future canonical gate without a
temporary harness. Package and runtime work now inherit explicit branch,
testing, review, security, cleanup, and handoff laws before implementation.
