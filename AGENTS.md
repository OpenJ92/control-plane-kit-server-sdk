# control-plane-kit-server-sdk Agent Guide

Canonical contract: `cpk-agent-contract/v1`

Source: [CPK #1741](https://github.com/OpenJ92/control-plane-kit/issues/1741).
This root guide carries the shared contract needed to work in this repository
without another checkout. Local SDK rules may tighten it; they may not weaken
authorization, Docker-only validation, truthful uncertainty, test ownership,
GitHub-memory, or redaction requirements.

## Shared Product Boundary

CPK is a human-authorized, AI-assisted infrastructure control plane. Providers
own external runtime truth. CPK owns topology, inspectable plans, execution of
approved actions, durable history, and truthful bounded reports.

- Provider reads and bounded reporting may be automatic.
- Consequential mutation requires an inspectable plan and appropriate user
  authorization.
- Destructive cleanup, public exposure, cost/capacity or credential changes,
  cross-provider movement, adoption, and ambiguous retries require explicit
  approval.
- Never blindly redispatch an interrupted or ambiguous external mutation.
- Never fabricate success, ownership, graph advancement, or cleanup.

This workload-facing SDK exposes bounded node-control contracts. It does not
grant control-plane, provider, topology, credential-custody, or autonomous
recovery authority.

## Durable Memory And Collaboration

GitHub issues, PRs, and material comments are durable project memory. Commits,
hashes, local logs, `/tmp` packets, inventories, task messages, and chat are
supporting coordinates only. Record decisions, releases, stops, evidence
meaning, reviews, and handoffs on the governing issue or PR.

When roles are assigned, North coordinates; Vale implements the bounded change;
Meridian reviews independently and reports findings-first `PASS` or `HOLD`.
Assignments and handoffs state the GitHub artifact, base/destination, scope,
suite/prerequisites, authority limits, stop conditions, and next reviewer.
Silence is not approval.

Keep implementation and review proportional. Tests prove SDK public contracts,
framework adapters, and security boundaries; they do not recreate Core or
Operations state machines, police helper layout, or turn fixture examples into
runtime invariants.

## Shared Validation And Stops

All executable validation uses the established Docker-backed `./test.sh`.
Pinned mode is normal; `local-core` requires the explicitly selected Core
checkout described by the script. Do not use host Python/PostgreSQL, venvs,
host `pip`, alternate databases, shims, or custom wrappers. If the suite or a
prerequisite is missing, cannot start, or fails for apparatus, stop and ask;
do not improvise, silently retry, rebaseline, or repair shared state.

One-shot wrappers, leases, live/provider-mutating gates, credential use, and
destructive cleanup require explicit issue-specific authority. Stop on
uncertain ownership, authority, base/destination, prerequisite, or effect
outcome.

`control-plane-kit-server-sdk` is the framework-neutral workload-facing SDK
for Control Plane Kit node control. It consumes the pure contracts published
by the pinned `control-plane-kit-core` distribution.

Core never imports the SDK.

The SDK does not own control-plane operations, server products, provider
effects, application truth, or the cpk-server process. Application and domain
packages may implement the SDK protocol while retaining ownership of their own
state and transactions.

## Branch Flow

Inherit only the branch topology in `GIT-FLOW.md`:

```text
main
  develop
    codex/<issue-id>-<slug>
```

Issue branches target `develop`. Promote `develop` to `main` only when a
coherent reviewed vertical is ready.

The canonical proportional-evidence contract in this guide supersedes the
legacy mandatory-red process in `GIT-FLOW.md`.

## Recursive Issue Loop

Use this calibrated loop for every non-trivial issue:

```text
current behavior and public contract
  -> smallest bounded implementation and proportional tests
    -> authoritative Docker-backed ./test.sh
      -> concrete review
        -> decision log and dependent handoff
```

Split an issue when it changes multiple public concepts, has unrelated test
groups, needs more than one decision log, or cannot be reviewed while holding
a small amount of state. Do not begin a dependent child before its predecessor
is accepted.

Tests must fail for missing behavior, not broken imports, collection, fixtures,
or Docker setup. Do not weaken assertions, hide collection, add `xfail`, point
tests at another implementation, or use skips to manufacture green evidence.
Use law cards and focused target-red evidence only for an explicitly governed
migration/parity issue or when a focused failure is needed to establish
causality for missing behavior.

## Package Ownership

The dependency direction is one-way:

```text
control-plane-kit-server-sdk -> pinned control-plane-kit-core
```

The base distribution remains framework-neutral. It must not depend on or
import control-plane operations, cpk-server, server products, Docker or
Cloudflare clients, Postgres stores, secret providers, or FastAPI.

The public extension model is exactly one
`ControlPlaneVariable[ReadResult, Command, TransitionResult]` protocol over accepted core
contracts. Do not introduce a second handler, plugin, reflection, arbitrary
method-call, URL, HTTP-body, or free-form mutation system.

Process-local implementations must say that they are not durable. Domain-owned
implementations retain their own UnitOfWork, ledger, replay, and transaction
semantics. Issue #1150 owns replay, cache, ledger, and idempotency-key
interpretation. Framework adapters, grant verification, and route accrual
belong to their named later issues. `coordination/foundation.json` is
historical genesis metadata, not a live coordination ledger.

Workload verifier public-key configuration is supplied process-local state. It
may retain bounded exact core `DelegationPublicKey` values for later signature
verification, but it does not prove producer provenance, graph admission,
issuer, audience, lifecycle status, authorization, or restart reconstruction.
Public PEM is non-secret but integrity-sensitive and remains absent from
routine representations and diagnostics.

## Testing

Use Docker-first validation and the Python standard-library `unittest`
framework. Do not use host Python, pytest, `xfail`, hidden collection, or
unapproved skips.

The checked-in `./test.sh` is the authoritative package gate. Do not replace it
with host execution or an ad hoc focused container command.

Test reports must distinguish focused, package, composition, source-live,
published, and provider-mutating evidence. A green count does not make those
proofs interchangeable.

## Review And Decision Logs

Every non-trivial pull request receives a skeptical review for correctness,
public API clarity, package boundaries, tests, security, secret redaction,
runtime cleanup, descriptor stability, and dependent handoff.

Record a concise decision log containing:

- chosen shape and important snippets;
- why it was chosen and alternatives rejected;
- owning validation and its exact reviewed coordinate;
- security and operational notes;
- residual risks; and
- the next issue handoff.

Do not merge merely because checks are absent or delayed. Exact-head checks,
review, and the issue acceptance gate must be terminal.

## Security

Every issue, pull request, and handoff includes an explicit security note, even
when no new security surface exists.

Repository artifacts, tests, logs, errors, examples, and descriptors must not
contain credentials, private keys, secret values, compact grants, signatures,
private endpoints, provider authority, or workflow tokens. Public verification
material is non-secret but integrity-sensitive and must still be bounded and
redacted from routine representations.

Authentication, authorization, graph admission, provenance, replay, network
exposure, and mutation authority must be explicit. Public package status,
private Docker networking, lexical validation, or route reachability is never
proof of authority.

## Docker Cleanup

Never use broad Docker prune. Inspect resources before and after Docker work,
remove only exact package-owned containers, networks, images, and volumes, and
preserve every unrelated or foreign container, network, volume, image, and
mapping.

## Handoffs

Leave a concrete handoff when a child changes what its dependent needs to know:
accepted coordinates, files and public decisions, tests, security assumptions,
remaining risks, and the next exact base.
