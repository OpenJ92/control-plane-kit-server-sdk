Source: [test_support/installed_verification_dependencies.py](../../../test_support/installed_verification_dependencies.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The installed-extra probe first imports the neutral root and checks no eager crypto import, then verifies exact direct PyJWT/cryptography distribution versions, imports all three optional verifier classes and confirms their defining module. Health admission is included in this availability check. Errors use the existing fixed rejection path. The probe does not validate signatures; real generated-key behavior belongs to tests/test_health_verification.py and the preserved legacy verifier suite. Fake-module gate fixtures test probe ordering, not real dependency behavior.

