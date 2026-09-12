Source: [test_support/installed_verification_dependencies.py](../../../test_support/installed_verification_dependencies.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The installed-extra probe first imports the neutral root and checks no eager crypto import, then verifies exact direct PyJWT/cryptography distribution versions, imports all three optional verifier classes and confirms their defining module. It also imports the neutral WorkloadNodeHealthReadDispatcher from health.py and rejects FastAPI/Starlette/AnyIO appearing in that verification-only process. Errors use the existing fixed rejection path. This establishes optional availability/framework isolation, not signature or callback execution; real behavior belongs to the package tests. Fake-module gate fixtures test probe ordering, not real dependency behavior.

SDK #26 additionally imports `_PreparedControlDispatch` from its defining shared module and checks framework isolation after that transitive framing/health import. It remains an installed optional-dependency probe, not dispatch execution.
