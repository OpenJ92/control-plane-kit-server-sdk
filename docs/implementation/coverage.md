# Initial SDK companion coverage

Source: develop 7a9cc5e104a2a310e78f0d4ec742dff78cdd8e79, [issue #18](https://github.com/OpenJ92/control-plane-kit-server-sdk/issues/18).
55 original tracked paths: 0 authored awaiting review, 20 reviewed, 16 pending, 19 excluded.
Source owners and selected imported Core contracts were read directly; test
navigation uses selected assertions. Vale independently reviewed the first eight
companions against their owners and the selected Core dependency; larger tests
received selected assertion review, not a full audit. Vale also approved the
three verifier-key/facade/test companions after full source and selected Core
owner reads, with targeted key-test assertions. No tests run.
North independently reviewed the two Vale-authored verification companions against
the full verifier owner, selected pinned Core laws and selected test assertions;
this is not a full large-test or transitive cryptography audit.
North also reviewed both replay companions against the full replay owner and
selected test assertions. The cancellation wording is scoped to the caught
dispatch, normalization and completion-clock paths; no universal cancellation
guarantee or executed validation is claimed.
North reviewed all three FastAPI owners and five companions, selected actual
Core 0ee72c3 admission/result contracts, and selected installation, authorization,
threadpool, route-preservation and bounded-error tests. This was not a full
audit of both large test files or an executed package/HTTP validation.
This inventory excludes new documentation itself and does not certify freshness.

| Source | Status | Disposition |
| --- | --- | --- |
| `.dockerignore` | pending | Assigned to Vale; not yet authored. |
| `.github/workflows/tests.yml` | pending | Assigned to Vale; not yet authored. |
| `.gitignore` | pending | Assigned to Vale; not yet authored. |
| `AGENTS.md` | excluded | Existing governance/navigation prose maintained directly; no recursive mirror. |
| `Dockerfile` | pending | Assigned to Vale; not yet authored. |
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
| `pyproject.toml` | reviewed | [Companion](pyproject.toml.md) |
| `src/control_plane_kit_server_sdk/__init__.py` | reviewed | [Companion](src/control_plane_kit_server_sdk/__init__.py.md) |
| `src/control_plane_kit_server_sdk/_fastapi_surface_routes.py` | reviewed | [Companion](src/control_plane_kit_server_sdk/_fastapi_surface_routes.py.md) |
| `src/control_plane_kit_server_sdk/_fastapi_variable_routes.py` | reviewed | [Companion](src/control_plane_kit_server_sdk/_fastapi_variable_routes.py.md) |
| `src/control_plane_kit_server_sdk/_replay.py` | reviewed | [Companion](src/control_plane_kit_server_sdk/_replay.py.md) |
| `src/control_plane_kit_server_sdk/atomic.py` | reviewed | [Companion](src/control_plane_kit_server_sdk/atomic.py.md) |
| `src/control_plane_kit_server_sdk/context.py` | reviewed | [Companion](src/control_plane_kit_server_sdk/context.py.md) |
| `src/control_plane_kit_server_sdk/fastapi.py` | reviewed | [Companion](src/control_plane_kit_server_sdk/fastapi.py.md) |
| `src/control_plane_kit_server_sdk/protocol.py` | reviewed | [Companion](src/control_plane_kit_server_sdk/protocol.py.md) |
| `src/control_plane_kit_server_sdk/py.typed` | reviewed | [Companion](src/control_plane_kit_server_sdk/py.typed.md) |
| `src/control_plane_kit_server_sdk/verification.py` | reviewed | [Companion](src/control_plane_kit_server_sdk/verification.py.md) |
| `src/control_plane_kit_server_sdk/verifier_keys.py` | reviewed | [Companion](src/control_plane_kit_server_sdk/verifier_keys.py.md) |
| `test.sh` | pending | Assigned to Vale; not yet authored. |
| `test_support/dependency_preflight.py` | pending | Assigned to Vale; not yet authored. |
| `test_support/installed_fastapi_dependencies.py` | pending | Assigned to Vale; not yet authored. |
| `test_support/installed_import.py` | pending | Assigned to Vale; not yet authored. |
| `test_support/installed_verification_dependencies.py` | pending | Assigned to Vale; not yet authored. |
| `test_support/package_integrity.py` | pending | Assigned to Vale; not yet authored. |
| `test_support/tests/test_dependency_preflight.py` | pending | Assigned to Vale; not yet authored. |
| `test_support/tests/test_gate_contract.py` | pending | Assigned to Vale; not yet authored. |
| `test_support/tests/test_package_integrity.py` | pending | Assigned to Vale; not yet authored. |
| `tests/approved_skips.json` | pending | Assigned to Vale; not yet authored. |
| `tests/test_atomic_variable.py` | reviewed | [Companion](tests/test_atomic_variable.py.md) |
| `tests/test_fastapi_control_routes.py` | reviewed | [Companion](tests/test_fastapi_control_routes.py.md) |
| `tests/test_fastapi_variable_routes.py` | reviewed | [Companion](tests/test_fastapi_variable_routes.py.md) |
| `tests/test_invocation_context.py` | reviewed | [Companion](tests/test_invocation_context.py.md) |
| `tests/test_package_foundation.py` | pending | Assigned to Vale; not yet authored. |
| `tests/test_process_local_replay.py` | reviewed | [Companion](tests/test_process_local_replay.py.md) |
| `tests/test_repository_policy.py` | pending | Assigned to Vale; not yet authored. |
| `tests/test_variable_protocol.py` | reviewed | [Companion](tests/test_variable_protocol.py.md) |
| `tests/test_verification.py` | reviewed | [Companion](tests/test_verification.py.md) |
| `tests/test_verifier_keys.py` | reviewed | [Companion](tests/test_verifier_keys.py.md) |
