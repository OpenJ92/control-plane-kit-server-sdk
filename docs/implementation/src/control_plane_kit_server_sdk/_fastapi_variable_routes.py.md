Source: [src/control_plane_kit_server_sdk/_fastapi_variable_routes.py](../../../../src/control_plane_kit_server_sdk/_fastapi_variable_routes.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This private adapter owns registry construction, shared request framing and the
variable READ/APPLY routes. Registry construction snapshots each live variable's
descriptor once, requires exact equality with its declaration entry and callable
read/apply methods, rejects duplicates, and installs one Core result codec per
entry. Empty or declared subsets are valid. The captured dictionary is private
conventional state, not a deeply immutable or hostile-object trust boundary;
trusted composition supplies declaration, variables and verifiers.

Transport requires bytes raw path/query, caps each at 1,024 bytes and rejects
any nonempty query. Headers must be a list of at most 64 exact byte pairs,
totalling at most 32 KiB, with exactly one Authorization using the exact Bearer
prefix. Streaming enforces a 16-KiB cumulative body cap and READ requires an
empty body. Chunk count and elapsed request time are not bounded here. Framing
and body extraction precede signature verification; APPLY candidate decoding
belongs to the verifier after authentication.

One explicit threadpool boundary covers synchronous verifier admission, exact
trusted receiving-target equality, registry lookup, invocation-context creation,
variable call/replay and result normalization. Thus a same-audience foreign
target gets 403 before local variable existence is disclosed; a valid local
missing variable gets 404. Every APPLY attempt authenticates before entering
the application-local [replay coordinator](_replay.py.md). READ has no replay.
Workload apply may mutate caller-owned durable state; this adapter does not own
that transaction or undo effects after a failed result.

Result normalization uses consumer Core 0ee72c3's codec, exact operation result
types, matching request ID/operation and compact ASCII JSON capped at 16 KiB.
Valid Core rejection/failure remains an HTTP 200 nominal result. Transport,
credential, locality, lookup, replay conflict/capacity and ordinary internal
exceptions use the fixed status/code table. Private helper exception chains or
process-control BaseExceptions are not universally sanitized for arbitrary
direct callers; HTTP responses omit their details.

Both routes are excluded from OpenAPI. Their private builders are not an
alternative public installer: [fastapi.py](fastapi.py.md) composes all four
routes and enforces host collision/startup constraints. No provider client,
graph authority, credential issuance or SDK persistence is added. See
[variable-route tests](../../tests/test_fastapi_variable_routes.py.md).
