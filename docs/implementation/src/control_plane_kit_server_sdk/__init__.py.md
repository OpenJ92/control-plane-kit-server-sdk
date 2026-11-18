Source: [src/control_plane_kit_server_sdk/__init__.py](../../../../src/control_plane_kit_server_sdk/__init__.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The neutral root exports invocation context, the one variable protocol, its atomic implementation, three nominal public-key-set/holder families and version0.1.0. Health adds exactly WorkloadNodeHealthReadVerifierKeySet and AtomicWorkloadNodeHealthReadVerifierKeySet from verifier_keys.py. Optional verification and FastAPI are not root imports or exports. Installed-root and foundation probes maintain that separation; importing the root is not signed admission or HTTP evidence.

## Behavior and evidence details

A root import is not evidence that optional extras are installed or their
routes have been admitted. Review [package metadata](../../pyproject.toml.md),
installed-import checks and each owner when changing exports. The existing
[protocol](protocol.py.md) and [key-set](verifier_keys.py.md) notes explain which
runtime and authority claims these values do not establish.
