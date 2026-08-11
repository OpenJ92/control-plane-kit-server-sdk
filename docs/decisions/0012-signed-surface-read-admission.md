# Decision 0012: Signed Surface-Read Admission

## Status

Accepted for issue #1542.

## Capability

`Ed25519WorkloadNodeControlSurfaceReadVerifier` authenticates one bounded
credential and reconstructs the exact `NodeControlSurfaceReadRequest` that the
credential authorizes. It supports both capabilities and status questions.
The returned value is ordinary core data, not an authenticated wrapper or a
lasting authority object.

The verifier consumes public verification material from
`WorkloadNodeControlSurfaceReadVerifierKeySet`, whose purpose is exactly
`WORKLOAD_NODE_CONTROL_SURFACE_READ`. The process-local atomic holder publishes
one complete key snapshot. Command keys and surface-read keys cannot substitute
for one another even when their key IDs and PEM material match.

## Credential Profile

The compact token type is
`CPK-WORKLOAD-NODE-CONTROL-SURFACE-READ+JWT`. The exact signed payload member is
`workload_node_control_surface_read`. The whole credential is limited to 4,096
bytes, with 512-byte protected-header, 3,840-byte payload, and 128-byte
signature-segment ceilings. Canonical base64url spelling, duplicate-aware JSON,
closed object profiles, bounded depth, and bounded member count are checked
before maintained Ed25519 verification.

After signature verification, outer issuer, audience, time, JTI, and key ID
must agree exactly with the embedded grant. One trusted clock establishes the
half-open validity interval. The route kind and every request field must agree
with the grant before the request is returned. All failures become one fixed,
bounded, cause-free error that excludes credential, key, address, declaration,
and request material.

## Ownership

Admission is stateless. A valid credential may be admitted again while it
remains temporally valid; this verifier has no cache, ledger, replay store,
registry, persistence, or effects. It holds no private key.

The exact `candidate=None` input is a framework-neutral no-payload assertion.
It does not claim to enforce HTTP bodylessness. Issue #1507 owns HTTP extraction
and framing, live registry lookup, result construction, and execution of the
admitted read. It must preserve admission before those outer operations.
