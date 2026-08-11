# Decision 0013: Private FastAPI Variable Routes

Status: Accepted

Issue #1551 implements the authenticated READ/APPLY half of #1507 as a private
FastAPI interpreter. It does not publish a partial installer. Issue #1552 will
compose these routes with stateless capability/status reads and publish the one
preferred all-four installer.

## Chosen Shape

`_build_variable_routes` receives trusted process-composition values: one exact
`NodeControlTarget`, one immutable surface declaration, a tuple of live
variables, one command verifier, and one application-local replay coordinator.
It snapshots each variable descriptor once and returns exactly two `APIRoute`
values:

```text
GET  /__control/variables/{variable_name}
POST /__control/variables/{variable_name}/commands
```

The interpreter order is fixed:

```text
bounded raw path and query rejection, headers, and streamed body
  -> signed admission
    -> exact trusted target equality
      -> immutable registry lookup
        -> one worker-thread interpretation
          -> strict core result normalization
```

APPLY passes through the accepted #1506 replay algebra. A malformed or failed
dispatch therefore converges to a replayable `NodeControlFailed` value rather
than an adapter-specific failure. READ has no replay state.

## Boundaries

The `fastapi` optional extra pins only the three named direct dependencies:
`PyJWT==2.13.0`, `cryptography==50.0.0`, and `fastapi==0.141.1`. The SDK root
does not import FastAPI, Starlette, AnyIO, JWT, or cryptography. The private
module is intentionally absent from `__all__`.

No credential, request candidate, target identity, provider exception, or
variable result is rendered in an error. Transport and interpretation failures
use a small closed status/code table. Authenticated APPLY deliberately invokes
caller-owned mutation and may therefore change process-local or durable
workload-owned state. The adapter adds no SDK-owned persistence, transaction,
graph authority, or provider client.

## Alternatives Rejected

- Audience-only authorization was rejected because it cannot prove which exact
  workload target received the HTTP call.
- Registry lookup before target binding was rejected because it leaks local
  variable existence across valid same-audience grants.
- Event-loop execution was rejected because verification, replay waits, and
  workload variables are synchronous.
- A public two-route installer was rejected because it would become a plausible
  but incomplete alternative to #1552's final all-four surface.
