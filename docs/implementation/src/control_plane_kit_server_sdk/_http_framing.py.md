Source: [src/control_plane_kit_server_sdk/_http_framing.py](../../../../src/control_plane_kit_server_sdk/_http_framing.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This private owner contains the existing control error bytes, framing exceptions and limits: 16-KiB body, 32-KiB/64 headers, 1024-byte path/query. Query input is exact bytes and must be empty. Header input retains the exact list/tuple/bytes shape and duplicate count; exactly one nonempty exact Bearer credential is required. No values are logged or reflected. These functions moved unchanged from the variable adapter.

There is no HTTP server, stream reader, path normalizer, timeout or framework import here. ASGI stream collection and response creation stay in the existing adapters; later stdlib framing is not implemented. The verification-only installed probe imports this owner transitively through shared dispatch while rejecting FastAPI/Starlette/AnyIO.
