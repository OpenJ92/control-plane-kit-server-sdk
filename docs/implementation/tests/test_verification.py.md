Source: [tests/test_verification.py](../../../tests/test_verification.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This unittest owner covers the two optional signed verifiers using generated
test Ed25519 keys, actual PyJWT admission and exact pinned Core requests/grants.
Raw JSON and compact-token helpers construct malformed, duplicated or
noncanonical inputs. Injected library/codec/clock calls make rejection ordering
observable; this is local credential validation, not live CPK/provider authority.

Command cases protect canonical framing, segment/type bounds, closed profiles,
duplicate members, one key snapshot, outer/embedded claim congruence and exact
route/request bindings. Bad signatures and invalid times must reject before
APPLY candidate decoding. Candidate failures then exercise the real request
codec. A trusted clock is read once per admission, with equality at expiry
rejected. Exact public errors omit test markers, have empty extra fields and
retain neither cause nor context.

Surface-read cases keep command/gateway/other authority families distinct, bind
kind/declaration/target/request identity and require candidate=None before
collaborators. Repeated valid admission is deliberately allowed: no replay state
is installed by the verifier. Controlled thread/Event cases replace the key
holder while PyJWT is blocked and require one in-flight call to retain its
original complete snapshot. This is a selected concurrency schedule, not durable
rotation, process restart or a distributed replay proof.

The test inventory also contains dependency/root-laziness and documentation
assertions. Those structural checks are distinct from cryptographic tests and
from the installed-package gate. This companion used selected substantive
assertions from the large file, with the full
[verification owner](../src/control_plane_kit_server_sdk/verification.py.md)
and selected Core 0ee72c3 codecs/comparison laws checked; it is not a full audit
of every fixture permutation or transitive cryptographic implementation.
Executable validation belongs to the repository's Docker-backed test.sh.
