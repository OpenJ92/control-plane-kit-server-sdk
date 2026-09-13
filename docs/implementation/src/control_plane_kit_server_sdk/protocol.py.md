Source: [src/control_plane_kit_server_sdk/protocol.py](../../../../src/control_plane_kit_server_sdk/protocol.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This runtime-checkable structural protocol is the SDK's command-variable
extension surface: descriptor, read and apply over existing Core request/result values.
Implementations conform without inheriting a framework or storage base class.
Read/transition results are covariant; the request parameter is contravariant.
Runtime membership proves member presence, not signatures or result validity.

The separate closed liveness/readiness callbacks in [health.py](health.py.md)
do not introduce another variable protocol or arbitrary mutation interface.

Every implementation must enforce command is context.request before apply work.
Equality is insufficient. Mismatch produces context-keyed INVALID_COMMAND
rejection without candidate rendering or domain mutation; the protocol states
that law but does not execute an implementation's method for it.

[Decision 0006](../../../../docs/decisions/0006-variable-protocol.md)
records why both arguments remain. Domain owners keep their own transactions,
ledger and replay; the SDK supplies neither through this interface.
[atomic.py](atomic.py.md) is one process-local implementation. The
[protocol tests](../../tests/test_variable_protocol.py.md) use a fake durable
owner to demonstrate conformance, not a real database transaction.
