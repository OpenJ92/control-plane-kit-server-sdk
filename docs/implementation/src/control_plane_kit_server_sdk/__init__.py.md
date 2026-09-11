Source: [src/control_plane_kit_server_sdk/__init__.py](../../../../src/control_plane_kit_server_sdk/__init__.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This facade exports the framework-neutral context, structural variable protocol,
atomic variable and both verifier-key-set/holder families, plus package version.
It imports their owners directly and does not import optional verification or
FastAPI modules. Preserve root identity rather than adding duplicate wrapper
types or a parallel extension surface.

A root import is not evidence that optional extras are installed or their
routes have been admitted. Review [package metadata](../../pyproject.toml.md),
installed-import checks and each owner when changing exports. The existing
[protocol](protocol.py.md) and [key-set](verifier_keys.py.md) notes explain which
runtime and authority claims these values do not establish.
