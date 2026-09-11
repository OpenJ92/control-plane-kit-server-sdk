# Initial SDK companion coverage

Source: develop 7a9cc5e104a2a310e78f0d4ec742dff78cdd8e79, [issue #18](https://github.com/OpenJ92/control-plane-kit-server-sdk/issues/18).
55 original tracked paths: 8 authored, 0 reviewed, 28 pending, 19 excluded.
Source owners and selected imported Core contracts were read directly; test
navigation uses selected assertions. Peer review remains pending. No tests run.
This inventory excludes new documentation itself and does not certify freshness.

| Source | Status | Disposition |
| --- | --- | --- |
| `.dockerignore` | pending | Assigned to North; not yet authored. |
| `.github/workflows/tests.yml` | pending | Assigned to North; not yet authored. |
| `.gitignore` | pending | Assigned to North; not yet authored. |
| `AGENTS.md` | excluded | Existing governance/navigation prose maintained directly; no recursive mirror. |
| `Dockerfile` | pending | Assigned to North; not yet authored. |
| `GIT-FLOW.md` | excluded | Existing governance/navigation prose maintained directly; no recursive mirror. |
| `README.md` | excluded | Existing governance/navigation prose maintained directly; no recursive mirror. |
| `coordination/foundation.json` | excluded | Historical genesis coordination metadata; not a current runtime or work ledger. |
| `docs/decisions/0001-repository-foundation.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `docs/decisions/0002-repository-policy.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `docs/decisions/0003-distribution-foundation.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `docs/decisions/0004-package-integrity-and-ci.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `docs/decisions/0005-invocation-context.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `docs/decisions/0006-variable-protocol.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `docs/decisions/0007-atomic-control-plane-variable.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `docs/decisions/0008-workload-verifier-public-material.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `docs/decisions/0009-verification-dependency-proof.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `docs/decisions/0010-signed-workload-node-control-admission.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `docs/decisions/0011-process-local-node-control-replay.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `docs/decisions/0012-signed-surface-read-admission.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `docs/decisions/0013-private-fastapi-variable-routes.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `docs/decisions/0014-atomic-fastapi-control-route-installation.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `docs/security/0001-foundation-review.md` | excluded | Existing decision/security prose remains its authoritative document. |
| `pyproject.toml` | authored | [Companion](pyproject.toml.md) |
| `src/control_plane_kit_server_sdk/__init__.py` | pending | Assigned to North; not yet authored. |
| `src/control_plane_kit_server_sdk/_fastapi_surface_routes.py` | pending | Assigned to North; not yet authored. |
| `src/control_plane_kit_server_sdk/_fastapi_variable_routes.py` | pending | Assigned to North; not yet authored. |
| `src/control_plane_kit_server_sdk/_replay.py` | pending | Assigned to North; not yet authored. |
| `src/control_plane_kit_server_sdk/atomic.py` | authored | [Companion](src/control_plane_kit_server_sdk/atomic.py.md) |
| `src/control_plane_kit_server_sdk/context.py` | authored | [Companion](src/control_plane_kit_server_sdk/context.py.md) |
| `src/control_plane_kit_server_sdk/fastapi.py` | pending | Assigned to North; not yet authored. |
| `src/control_plane_kit_server_sdk/protocol.py` | authored | [Companion](src/control_plane_kit_server_sdk/protocol.py.md) |
| `src/control_plane_kit_server_sdk/py.typed` | authored | [Companion](src/control_plane_kit_server_sdk/py.typed.md) |
| `src/control_plane_kit_server_sdk/verification.py` | pending | Assigned to North; not yet authored. |
| `src/control_plane_kit_server_sdk/verifier_keys.py` | pending | Assigned to North; not yet authored. |
| `test.sh` | pending | Assigned to North; not yet authored. |
| `test_support/dependency_preflight.py` | pending | Assigned to North; not yet authored. |
| `test_support/installed_fastapi_dependencies.py` | pending | Assigned to North; not yet authored. |
| `test_support/installed_import.py` | pending | Assigned to North; not yet authored. |
| `test_support/installed_verification_dependencies.py` | pending | Assigned to North; not yet authored. |
| `test_support/package_integrity.py` | pending | Assigned to North; not yet authored. |
| `test_support/tests/test_dependency_preflight.py` | pending | Assigned to North; not yet authored. |
| `test_support/tests/test_gate_contract.py` | pending | Assigned to North; not yet authored. |
| `test_support/tests/test_package_integrity.py` | pending | Assigned to North; not yet authored. |
| `tests/approved_skips.json` | pending | Assigned to North; not yet authored. |
| `tests/test_atomic_variable.py` | authored | [Companion](tests/test_atomic_variable.py.md) |
| `tests/test_fastapi_control_routes.py` | pending | Assigned to North; not yet authored. |
| `tests/test_fastapi_variable_routes.py` | pending | Assigned to North; not yet authored. |
| `tests/test_invocation_context.py` | authored | [Companion](tests/test_invocation_context.py.md) |
| `tests/test_package_foundation.py` | pending | Assigned to North; not yet authored. |
| `tests/test_process_local_replay.py` | pending | Assigned to North; not yet authored. |
| `tests/test_repository_policy.py` | pending | Assigned to North; not yet authored. |
| `tests/test_variable_protocol.py` | authored | [Companion](tests/test_variable_protocol.py.md) |
| `tests/test_verification.py` | pending | Assigned to North; not yet authored. |
| `tests/test_verifier_keys.py` | pending | Assigned to North; not yet authored. |
