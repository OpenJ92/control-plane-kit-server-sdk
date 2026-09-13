Source: [test_support/installed_verification_dependencies.py](../../../test_support/installed_verification_dependencies.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The installed-extra probe first imports the neutral root and checks no eager crypto import, then verifies exact direct PyJWT/cryptography distribution versions, imports all three optional verifier classes and confirms their defining module. It also imports the neutral WorkloadNodeHealthReadDispatcher from health.py and rejects FastAPI/Starlette/AnyIO appearing in that verification-only process. Errors use the existing fixed rejection path. This establishes optional availability/framework isolation, not signature or callback execution; real behavior belongs to the package tests. Fake-module gate fixtures test probe ordering, not real dependency behavior.

SDK #26 additionally imports `_PreparedControlDispatch` from its defining shared module and checks framework isolation after that transitive framing/health import. It remains an installed optional-dependency probe, not dispatch execution.

SDK #27 imports the public stdlib installer and verifies its defining module before the same framework-isolation check. Importing it must not bind a socket, start a listener or require FastAPI/Starlette/AnyIO; actual passive/listener behavior belongs to the owning stdlib tests.

## Behavior and evidence details

Ordinary exceptions in the import and metadata stages produce the fixed rejection
line and return 2. Explicit version/ownership mismatches use the same path.
Process-control BaseExceptions are outside those catches, and imported code's
own output/effects are not captured by this script. The probe does not hash
packages, inspect transitive versions, prove publisher identity or install
anything itself.

The [gate](../test.sh.md) supplies the separately installed verification extra.
[Gate-contract tests](tests/test_gate_contract.py.md) use resolver-free fake
modules/distribution metadata to check exact acceptance, early version rejection,
import order and bounded probe-emitted errors. Real dependency availability
requires the actual installed-extra phase; verifier behavior belongs to
[verification tests](../tests/test_verification.py.md).
