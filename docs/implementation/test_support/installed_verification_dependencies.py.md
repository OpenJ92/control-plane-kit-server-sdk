Source: [installed_verification_dependencies.py](../../../test_support/installed_verification_dependencies.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The probe first imports the SDK root and requires jwt/cryptography to remain
unloaded. It then compares installed distribution metadata to PyJWT 2.13.0 and
cryptography 50.0.0 before importing the optional verification owner and both
libraries. Finally, both verifier classes must report the SDK verification
module as their owner. Success reports import availability, not a signed-token
acceptance or rejection result.

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
