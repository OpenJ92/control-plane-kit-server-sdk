Source: [test.sh](../../test.sh).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The fail-fast Bash gate anchors itself to the repository root. It runs policy
self-tests, package integrity and structured dependency preflight in disposable
Python containers before building the test image. Preflight therefore blocks
unaccepted dependency metadata before package build or dependency-resolving pip;
it does not precede the policy image pull or all Docker effects.

Default pinned mode rejects an ambient CPK_CORE_REPO. Explicit local-core mode
requires that path to contain control-plane-kit-core, mounts the checkout
read-only and copies that package into each container for installation. This
is composition evidence, not proof of the metadata-selected Core source. The
same metadata preflight still runs first. Unsupported modes exit with code 2.

Three fresh named containers separate base, verification-extra and FastAPI-extra
installation. Each runs the installed-root probe from /tmp. Extra probes check
their named dependencies; only the FastAPI phase compiles source/tests and runs
the package unittest suite. Local-core installs explicitly name direct extra
versions and reinstall the SDK with --no-deps; pinned mode lets pip resolve the
declared dependency graph. Neither mode locks every transitive/build artifact.

The EXIT trap attempts removal of the three PID-named containers and test-image
tag, suppressing cleanup errors. There is no broad prune, registry push or
provider deployment. PID names are not a global ownership capability across
hosts sharing a daemon, and suppressed errors do not prove cleanup succeeded.
Read-only source mounts protect those mounted paths, not every host/runtime
resource. Pip/build network access remains part of actual gate execution.

See [preflight](test_support/dependency_preflight.py.md),
[integrity](test_support/package_integrity.py.md) and
[gate-contract tests](test_support/tests/test_gate_contract.py.md). Static phase
assertions, fake-Docker preflight tests and resolver-free probe fixtures establish
different evidence from an actual Docker-backed package run. No gate was executed
to produce these documentation companions.
