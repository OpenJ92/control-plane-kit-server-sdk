# Decision 0010: Signed Workload Node-Control Admission

Status: Accepted for the workload verifier boundary.

## Decision

`Ed25519WorkloadNodeControlVerifier` is the one optional credential-admission
object. It accepts only canonical three-segment compact credentials whose type
is `CPK-WORKLOAD-NODE-CONTROL+JWT`, takes one complete public-key snapshot, and
uses maintained `PyJWT==2.13.0` with `cryptography==50.0.0` for Ed25519
signature admission.

Before cryptographic admission, bounded structural inspection rejects malformed
framing, noncanonical base64url spelling, duplicate JSON members, excessive JSON
depth or member count, and material outside the closed header/payload/grant
profile. After authentication, exact outer and embedded grant claims must agree.
The verifier reads one trusted clock, checks the half-open grant interval, and
then enforces the complete core grant/request and route binding. For APPLY,
authentication precedes candidate decoding.

Every failure becomes one bounded categorical exception with cleared exception
links. Credentials, signatures, candidates, public PEM, key identity, nested
library errors, endpoints, and request material are never rendered. The holder
contains public verification material only; this boundary owns no private key.

## Ownership

The verifier authenticates one credential and returns one exact core
`NodeControlCommandRequest`. It does not prove graph membership, mint grants,
own lifecycle status, dispatch a command, mutate workload state, or expose a
network route. Replay is intentionally not interpreted here. Issue #1150 owns
replay, cache, ledger, idempotency-key interpretation, and authenticated route
accrual.

## Consequences

The SDK root remains lazy and does not export the optional verifier. Base
installation remains free of verification dependencies. The exact direct pins
do not lock transitive dependency versions, artifact hashes, or publisher
attestations.
