Source: [tests/test_verification.py](../../../tests/test_verification.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The existing real generated-key command/static verification tests are translated to the live receiver families under SDK43. #22 only adds the health verifier/error names to the two exact optional-module export inventories. Signature, framing, snapshot, clock, denial, candidate and error laws remain governing. Helpers are referenced by the new health test module without inheriting/recollecting these TestCases. Core exhaustive policy matrices remain Core-owned.

## Behavior and evidence details

This unittest owner covers the two command/surface optional signed verifiers using generated
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

Receiver helpers carry profile/context/declaration and installed expectations
are built independently. Historical raw families remain negative inputs. The
surface maximum uses a real socket-matching declaration, authority IDs of one
character and an eight-character request ID: the request reaches exactly951
bytes and grant1984 without widening any SDK framing ceiling. Kepler checked
this fixture arithmetic against accepted Core. Runtime replaces graph revision
inside target; original graph context is separate request data.

Candidate51dad05 gate36886008866 exposed that a wrong-purpose receiver grant
cannot be constructed as a Core value. The negative fixture now changes only
the embedded raw purpose descriptor before real signing, so the unchanged SDK
refusal assertion and subsequent common-PEM isolation test are actually reached.
This preserves Core's constructor law and does not forge a frozen grant. North's
PR44 release5934956351 authorizes this bounded test-only correction.
