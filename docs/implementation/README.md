# SDK implementation companions

SDK #76 starts from accepted develop `3192360c36934feadc37bb9ae3733ce7da755c31`
and selects accepted Core `7afef43f3d3b981094e37dcb3062b6e3a4f3d674` for the
Servers #351 provider-policy public-integration cohort. Since `c7b16007`, Core
changes only operations HTTP, parity and projection catalogues; SDK-consumed
receiver, wrapper, signing, health and route contracts are unchanged. Metadata,
the strict guard and existing provenance/rejection expectations move together.
The unchanged pinned owner gate must establish compatibility and import
isolation. Secrets #83 waits for the actual accepted SDK successor, followed by
Interpreters #234 and Servers #351. No runtime SDK, extra, runner, publication,
credential or provider-effect change is included. Earlier adoption accounts
below remain historical evidence.

SDK #74 starts from accepted develop `cd4722fbfb942e7c2467a39b3cd0e32ded4a90ac`
and selects accepted Core `c7b16007467085be997f8dc3025e90e78649b00a` for the
provider-policy client cohort. Since `fec0816`, Core adds only the pure
provider-policy module and root exports; consumed workload contracts are
unchanged. Metadata, strict guard and existing provenance/rejection expectations
move together. The unchanged pinned owner gate must establish compatibility
and import isolation. Secrets #81 waits for the actual accepted SDK successor;
Interpreters #232 follows. No runtime SDK, extras, runner or publication changes.
The earlier adoption accounts below remain historical evidence.

SDK #72 starts from accepted develop `464df26c568971362eb3a08abaf9dfc227a4ddbb`
and selects accepted Core `fec0816281aeb83ede98616adcc4f96dfe5777a8` for Servers #349.
Against prior Core `4cc1716bef4d7548ddb4cd343e53fa06bb447104`, only operations HTTP,
parity and projection catalogues change (ten production lines); workload
receiver, wrapper, health, verification and route contracts are unchanged.
Active metadata, strict preflight and existing coordinate expectations move
together without weakening negative cases. The unchanged pinned owning gate
must prove resolution, compatibility and import isolation before acceptance.
Secrets #77 consumes the accepted SDK successor, then Interpreters #230 and
Servers #349 follow. No production SDK behavior, extras, gate or publication
changes. Earlier adoption accounts below are historical provenance.

SDK #70 starts from accepted develop `43838fd0f4391428cfffa87f8c4dbd5cc6d5eab1`
and selects accepted Core `4cc1716bef4d7548ddb4cd343e53fa06bb447104`. The Core
production delta from the prior `879efb95` selection is limited to operations
HTTP/parity/projections; SDK receiver, wrapper, health, key, route definitions
and root exports are unchanged. Active metadata, exact preflight/foundation
expectations and pin-bearing companions move together. Existing pinned
base/verification/FastAPI installations and the owning package gate establish
compatibility; no new test merely mirrors the version string. Secrets #72
waits for this issue's accepted SDK merge, followed by Interpreters #228 and
Servers #341. Historical coordinates below remain provenance.

Follow the [cross-repository convention](https://github.com/OpenJ92/control-plane-kit/issues/1799)
and [SDK issue #18](https://github.com/OpenJ92/control-plane-kit-server-sdk/issues/18).
Map each covered source path below this directory and append .md. Read the note,
source and selected imported contracts before changing code; maintain them in
the same source change. Use the actual diff and existing PR decision log for
review. Coverage in [coverage.md](coverage.md) is an initial rollout inventory,
not a permanent freshness ledger or a claim of full behavior audit.

Read [context](src/control_plane_kit_server_sdk/context.py.md), then
[protocol](src/control_plane_kit_server_sdk/protocol.py.md), then
[atomic variable](src/control_plane_kit_server_sdk/atomic.py.md) for the neutral
extension boundary. Continue through [verification](src/control_plane_kit_server_sdk/verification.py.md),
[process-local replay](src/control_plane_kit_server_sdk/_replay.py.md), and
[optional FastAPI installation](src/control_plane_kit_server_sdk/fastapi.py.md)
for the separate admission, deduplication and HTTP owners. The invocation
context is not an authority token. [The package gate](test.sh.md) and its support
companions distinguish source checks, installed-package evidence and live
runtime acceptance.

SDK #30 started from accepted develop `e822df4ddd4093f6129c65c8fc0707841a84dc51`
and selected Core `b79a02d1ac8ef987dd34abeb2297a231b109f7a6`.
SDK #34 starts from develop `2a5fcf54c2768114a7a484abb4f4c5d1dfe19410`
and selects Core `e074bda49fa0c46f420d675e45a93f787b460c02`. Its source
delta is confined to Core management planning compilation and observations;
the SDK-consumed control, health and key definitions are unchanged. The
unchanged owner gate must establish compatibility and import isolation.
SDK #36 starts from accepted develop `d8b72e52c8ebca65bf21a2a2ae51df663b1c8a77`
and selects Core `f1e6cf2420bf2ec381aab745f462d4e64baef5fc`. The exact delta
since #34 touches operations HTTP/lifecycle/parity/recovery and planning/saga;
the SDK-consumed control, health, key and route-template definitions are
unchanged. Pin-bearing companions reflect the selected coordinate; their
behavioral accounts were reviewed with no semantic change. The ordinary pinned
gate must establish compatibility and import isolation before acceptance.
The original rollout reviewed `7a9cc5e104a2a310e78f0d4ec742dff78cdd8e79`
with Core `0ee72c3fcdfbee5094357152bdf070fbfc53393c`; that is historical
review provenance, not the current dependency. Selected direct dependencies
and optional extras are recorded by [pyproject.toml](pyproject.toml.md).
Consumer adoption requires rereading the relevant imported contracts.

The completed health/host slices add [neutral health dispatch](src/control_plane_kit_server_sdk/health.py.md),
[shared preparation/interpretation](src/control_plane_kit_server_sdk/_control_dispatch.py.md),
[bounded byte framing](src/control_plane_kit_server_sdk/_http_framing.py.md),
and the [passive standard-library installer](src/control_plane_kit_server_sdk/stdlib.py.md).
FastAPI and stdlib reuse signed admission and workload semantics rather than
introducing a second verifier or replay owner. Health-only, mixed and legacy
composition are distinct; SDK package evidence does not prove product adoption,
custom-host equivalence, native supervision or provider/live acceptance.

Existing AGENTS guidance contains historical references to later route,
verification and replay issues; current source already includes those owners.
Interpret historical decisions by their named boundary and verify current
source before treating deferral text as current implementation status. This is
a documentation discrepancy to preserve in issue/PR handoff, not authority to
change security or execution rules.

SDK #43 migrates the existing live receiver stack to Core 1f28d009's receiver
configuration/requests/grants and correlated results. Touched owner companions
record the source changes and fixture translations. Historical decisions and
prior acceptance coordinates remain provenance; README and current owners state
the supported transport matrix. O3/controller command delivery is outside this
SDK change. PR #44 owns candidate gate/review evidence.

SDK #45 selects accepted Core1916 merge
`250d65e19dc748ebe840f705be77eb732dab3cb3`. Only Core's gateway advertisement
production owner changed; SDK receiver imports and behavior are unchanged.
Dependency/preflight/foundation coordinates and pin-bearing companions are
updated together. Existing foundation/preflight test companions reflect the new
coordinate with no behavioral change. The ordinary pinned gate owns adoption evidence;
Secrets43 waits for the actual accepted SDK merge.

SDK #47 starts from accepted develop
`5dc93b92c27bb9bbe2af027f945a347e5e4131bc` and selects accepted Core
`da17efb1303ed2176374548dd998d19a655055bf`. The exact Core source delta adds
configuration instance/invocation contracts and updates approval, planning and
runtime-effect owners. The SDK's imported receiver, wrapper, health, key and
route contracts and Core root exports are unchanged. Active metadata,
preflight, test and companion pins move together; historical coordinates above
remain provenance. SDK source, direct extras and the owning gate are unchanged.
Pinned base/verification/FastAPI installation and package evidence belong in the
PR. Secrets45 needs the actual accepted SDK47 merge, not this branch or Core's
merge alone; Interpreters180 follows. No I177 replacement/cleanup or live
capability is established by this adoption.

Servers #237's shared-contract alignment checkpoint starts from accepted SDK
develop `447a3c4c5a20b5c56402c813f6cfde1685eefda0` and selects common Core
`ba0bd45e7fa7673b837366f7f5da5f9159b0dee8`. Compared with SDK47's `da17efb`
selection, Core changes planning compiler/management compiler and their exports,
and adds receiver-management routes and installation receipts. Existing
SDK-consumed receiver, wrapper, health, key and route definitions are unchanged;
Core root additions still require ordinary installed import-isolation evidence.
The live SDK source, extras and owning `test.sh` remain unchanged. Only metadata,
exact-coordinate preflight/foundation expectations and current pin-bearing
companions move; historical coordinates above remain provenance. The next
Secrets pin must select the actual accepted SDK* together with this C*.
Interpreters #186 and Servers #245 remain later owners. No receipt production,
full #237 completion, dependency override, package/image publication or provider
mutation is implied by the metadata update.

The next Servers #237 alignment starts from accepted SDK develop
`23500b1445dc6a748bd92a441e781d7f9ed90299` and selects accepted Core #1969
`a3f212063b0eb83f08599fc729c05c473aa5a1ef`. Against the prior `ba0bd45e`
selection, Core adds only a structural declared-slot selector and root export.
The SDK wrapper's actual V2 decoder and other imported contracts are unchanged;
SDK source, extras and the owning gate remain unchanged. Metadata, exact pin
assertions and current companions move together. Prior coordinates above remain
historical evidence. The owning pinned Docker gate and independent review must
establish package adoption before Secrets selects the accepted SDK merge.
This supplies dependency alignment for the Operations declared/actual split;
it does not prove Servers #237 runtime acceptance or the live grandparent test.

Servers #249's retained-update alignment starts from accepted SDK develop
`f1bc730a7b244d7a713eb4a6531a5fb5fb76eee0` and selects accepted Core/O1 #1981
`fe8d44fa09eed7d0d3df70f7782203f3045f9c15`. Against `a3f21206`, Core changes
the managed-update compiler and adjacent export formatting; SDK-consumed receiver,
wrapper, health, key and route definitions remain unchanged. No SDK source/test
caller uses the removed content-only compiler. Runtime source, extras and owning
gate are unchanged. Metadata, exact preflight/foundation assertions and current
pin-bearing companions move together. Historical coordinates remain provenance.
The ordinary hosted pinned gate owns adoption evidence; Secrets must consume
the accepted SDK merge before Interpreter and Servers adoption. This dependency
step creates no new runtime, authority, credential or provider surface and does
not prove the later S1 process replacement.

SDK #52 / Servers #251's image-update alignment starts from accepted SDK develop
`a35e3a50b0beb6043284847a2dde4f7eaa2f945c` and selects accepted Core
`05b5f28a624e6e03f1dadbe6ad77ece2bec09601`. Against `fe8d44fa`, only Core's
managed-update compiler production module changes, adding the closed image
transition. SDK-consumed receiver/wrapper/health/key/route/receipt contracts are
unchanged; SDK production source does not import that compiler. Runtime source,
extras and owning gate remain unchanged. Metadata, exact preflight/foundation
assertions and current companions move together; historical coordinates above
remain provenance. The ordinary pinned gate and independent exact-head review
must pass before North accepts the SDK successor for Secrets. This does not
publish a package/image, authorize provider effects or accept Servers #251.

The selected-secret alignment starts from accepted SDK develop
`9aa01ef7b2df6106f6ad87c1625a7feb93394b88` and selects Core/Operations #1988
`87e231c661879e44816ba71ff9320c040c868d60`. Core adds secret selections,
consumer grants and installation receipts with planning/runtime integration.
The SDK-consumed receiver, wrapper, health and key contracts remain unchanged;
production SDK source does not consume the new secret installation contracts.
Exact metadata, preflight, positive/negative expectations and current companions
move together. Historical coordinates above remain provenance. The unchanged
owning pinned Docker gate must prove installation and import compatibility.
Secrets must adopt the actual accepted SDK merge and the same Core before
Interpreters #190/#191 can assemble their package dependencies. This is a
compatibility prerequisite, not secret-recipient or live deployment evidence.

SDK #56 starts from accepted develop
`ad0582937d7e41f1e7a41295fa1de58c2ce4cba2` and selects accepted Core #1991
`5b66dcac4bf2cf76219efaf05fa5ff06588bd16a`. The exact production delta from
`87e231c6` changes only `planning/management_compiler.py`; SDK production code
does not import this compiler. Receiver, wrapper, health, key and route
contracts consumed by the SDK are unchanged. Metadata, dependency preflight,
positive/negative coordinate expectations and current pin-bearing companions
move together. Historical coordinates above remain provenance. No runtime
source, extras or gate changes. The ordinary pinned Docker gate must establish
compatibility and import isolation; Secrets #54 uses the actual accepted SDK
merge, then Interpreters #201 and Servers #252 adopt the coherent tuple. No
provider effects, installation receipts or live acceptance follow from this pin.

SDK #58 starts from accepted develop
`d4cbbb16a4ce47bae0b791adab5de8940355ea99` and selects accepted Core/Operations
`012a7b8b7cc153cbf17b1a62513fab747eaad782` for Servers #253. Since the prior
`5b66dcac` selection, the only Core production delta is
`planning/management_compiler.py`: the closed retained-verifier refresh relation.
SDK source does not import that compiler; its receiver, wrapper, health, key
and route contracts and root exports are unchanged. Metadata, exact preflight
and foundation expectations, README and current pin-bearing companions move
together. Existing positive/negative assertions, runtime source, extras and
owning gate are unchanged. Historical coordinates above remain provenance.
The normal pinned Docker gate must prove adoption and import isolation;
Secrets #56 then consumes the actual accepted SDK commit, followed by
Interpreters #203 and Servers #253. No installed refresh, producer authority,
key lifecycle, image publication or live grandparent acceptance is implied.

SDK #60 starts from accepted develop `e289d6939b7e6432ffa5181789b0600bf8e3ffe2`
and selects accepted Core `9861e536e79314005499ae07379f627bfb1599a2` for Servers
#254. Since the previous `012a7b8b` selection, the only Core production delta is
`planning/management_compiler.py`, adding the coupled health declaration/route
transition. SDK production source does not import that compiler; consumed
receiver, wrapper, grant and key contracts and root exports remain unchanged.
Metadata, exact preflight/foundation expectations and current pin-bearing
companions move together. Existing assertions, runtime code, optional extras
and owning gate remain unchanged. Normal pinned package evidence proves SDK
adoption/import isolation; Secrets #58 then selects the actual accepted SDK
merge, followed by Interpreters #205 and Servers #254. This does not prove
installed declaration cutover, publish an image, or accept the grandparent run.

SDK #62 starts from accepted develop `d4e7c4d91c054f139e2971774ae5e37fc741262d`
and selects accepted Core #2005 merge `73d87e99bf711ff8a88112ca56c5eee8055ac5b7`.
Since `9861e536`, Core changes topology secret-selection carry-forward and
extracts the existing pure health-declaration relation into receiver
configuration for planner reuse. The SDK wrapper loads and decodes through the
unchanged receiver value/codec; it does not call the new private relation or
secret-selection authoring. Signed admission contracts and root exports remain
unchanged. Runtime code, extras and the ordinary pinned gate are unchanged;
metadata, preflight/foundation expectations and current companions move together.
The owning gate must prove installed SDK compatibility before Secrets adopts
the actual accepted SDK merge. The already qualified Hello image keeps its
historical SDK/Core provenance and requires no republication. Servers #254's
coupled runtime proof remains a later boundary.

SDK #64 starts from accepted develop `1657cb91b143931bafcdb32108950d2bbbb66d95`
and selects accepted Core `ec61e2b17c3a3f1bdea1dd6bc8fc64ac1b9528b0`.
Since `73d87e99`, Core adds required configuration slots, declared selection,
product/material validation and related secret-selection composition, plus two
root exports. SDK setup still consumes actual receiver configuration through
the unchanged value/codec; signed receiver/grant contracts are unchanged.
Metadata, the exact preflight guard, positive/negative coordinate expectations
and current companions move together. No SDK runtime, extras or runner changes.
The ordinary pinned gate must establish installed compatibility and import
isolation, followed by exact owned-resource cleanup verification. Secrets #62
then adopts the actual accepted SDK merge, followed by Interpreters #211 and
Servers #280. Package adoption neither changes historical image provenance nor
establishes managed-image or live grandparent acceptance.

SDK #66 starts from accepted develop `eff09090755eb21028695f0224eec7b81f2db535`
and selects accepted Core `955666898218e4f2956b6e9fcd33bdba97ffdb06`.
Since `ec61e2b`, Core adds the pure retained-image ingress compiler and its
root/planning exports. SDK-consumed receiver, wrapper, grant, health and key
contracts are unchanged. Operations in that archive is not installed by the
Core subdirectory dependency. Current metadata, strict preflight, positive and
negative coordinate expectations and companions move together. Historical
coordinates above remain provenance. SDK runtime, extras, runner and workflows
are unchanged. The normal pinned Docker gate must prove installed compatibility
and import isolation. Secrets #64 then adopts the actual accepted SDK merge
with the same Core before Interpreters #214 can run its semantic target gate.
This alignment creates no new credential/provider authority and proves no
published image or live deployment behavior.

SDK #68 starts from accepted develop `cad5cc3dacbff1da79e6cc8b4c0c88526363e033`
and selects accepted Core `879efb9576ac0580a6236d0a7372c036537b4dfe`.
Since `95566689`, Core changes control-plane command/HTTP/parity/projection facts
and adds the provision policy scope. Core root exports and SDK-consumed receiver,
wrapper, signing, health and route contracts are unchanged. Metadata, exact
preflight, positive/negative coordinate expectations and current companions move
together; historical adoption notes remain provenance. SDK runtime, extras,
runner and workflows are unchanged. Normal pinned Docker CI must establish
installation, import isolation and existing package behavior before the actual
accepted SDK merge is selected by Secrets #68, then Interpreters #222 and Servers
#313. This prerequisite does not enable intake or change historical images.
