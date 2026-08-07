# Decision 0008: Workload Verifier Public Material

Status: Accepted for process-local supplied verifier configuration.

## Decision

`WorkloadNodeControlVerifierKeySet` is one immutable, slotted value containing
the exact workload-node-control key purpose and one to sixteen exact core
`DelegationPublicKey` values. It orders keys by exact key id while preserving
the key objects by identity. Before ordering, it rejects unexpected instance
fields and reconstructs each core value to prove canonical key id, normalized
PEM, and fingerprint congruence. Key ids and fingerprints are independently
unique. The public-key tuple is excluded from routine representation.

`AtomicWorkloadNodeControlVerifierKeySet` holds one complete key-set reference.
Construction and replacement accept only the exact key-set type. Replacement
validates before taking the lock, publishes one reference under the lock, and
returns that exact reference. Readers therefore observe only an old or new
complete snapshot during A, A+B, and B rotation.

## Ownership

This is supplied, process-local public verification material. It is not a
descriptor, codec, environment renderer, credential, lifecycle record, or
durable store. Trusted composition must provide a complete snapshot at every
process start. The value does not authenticate its producer and does not prove
provenance, graph admission, key status, or mutation authority.

Expected issuer and audience are signed-verifier policy, not key identity. The
held verifier predecessor owns that policy and authenticated grant admission.
Issue #1150 owns route accrual, replay, cache, ledger, and idempotency-key
interpretation. Core retains the provider-neutral key language and graph
authority references.

## Security And Operations

Public PEM is non-secret but integrity-sensitive. It remains available through
the explicit `public_keys` field for later verification, while key ids,
fingerprints, and PEM are absent from key-set and holder representations and
from categorical validation errors. Private keys, secret references,
signatures, compact grants, endpoints, provider clients, cryptographic
execution, lifecycle status, and restart reconstruction are absent.

The holder has no network listener, route, provider effect, transaction,
history, cleanup action, or cross-restart guarantee. Atomic publication does
not establish authentication, authorization, provenance, or graph membership.

## Consequences

A later signed verifier can consume a bounded current public-key snapshot
without making the SDK a key-lifecycle owner. Adding issuer/audience fields,
wire codecs, lifecycle states, token behavior, or another holder protocol
requires a separate public decision.
