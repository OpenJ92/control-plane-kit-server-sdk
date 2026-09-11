Source: [src/control_plane_kit_server_sdk/context.py](../../../../src/control_plane_kit_server_sdk/context.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This one-field frozen/slotted value retains the exact Core request by identity,
with the request omitted from repr. Its constructor rejects lookalikes and
subclasses using a categorical message without rendering the candidate.

It records what an outer adapter passed inward. It does not authenticate the
request, check graph membership, establish provenance, or prove that a verifier
ran. Exact top-level type admission is not a recursive revalidation of forged
Core objects. The selected Core owner supplies the request language; see the
[dependency declaration](../../pyproject.toml.md) before adopting upstream changes.

[Decision 0005](../../../../docs/decisions/0005-invocation-context.md)
records this neutral trust boundary. [protocol.py](protocol.py.md) requires
apply implementations to compare the separately supplied command with
context.request by identity before work.
