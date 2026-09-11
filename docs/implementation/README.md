# SDK implementation companions

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

Initial source coordinate: develop 7a9cc5e104a2a310e78f0d4ec742dff78cdd8e79.
The metadata selects Core 0ee72c3fcdfbee5094357152bdf070fbfc53393c.
The first batch checked request, state and variable-descriptor contracts from
that Git object, not the newer Core documentation branch. Selected direct
dependencies and optional extras are recorded by [pyproject.toml](pyproject.toml.md);
consumer adoption requires rereading the relevant imported contracts.

Existing AGENTS guidance contains historical references to later route,
verification and replay issues; current source already includes those owners.
Interpret historical decisions by their named boundary and verify current
source before treating deferral text as current implementation status. This is
a documentation discrepancy to preserve in issue/PR handoff, not authority to
change security or execution rules.
