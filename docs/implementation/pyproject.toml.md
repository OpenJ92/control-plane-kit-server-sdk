Source: [pyproject.toml](../../pyproject.toml).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

SDK #62's selected-secret declaration compatibility alignment selects accepted Core/Operations
`73d87e99bf711ff8a88112ca56c5eee8055ac5b7`, matching the exact dependency-preflight
guard. Since the prior selection `9861e536`, Core changes secret-selection
carry-forward and extracts the existing pure health-declaration relation into
receiver_configuration.py for reuse by the planner. The SDK consumes that
module's unchanged receiver value/codec, not the new private relation. Its
wrapper, health, key, route and receipt contracts remain unchanged. SDK
production source imports neither secret-selection authoring nor the planner.
The ordinary pinned suite must establish adoption and import isolation. The
accepted SDK merge supplies SDK* for subsequent Secrets and Interpreters pins.
This pin does not add SDK behavior or complete Servers #254 acceptance.
SDK runtime behavior is unchanged. Verification still pins
PyJWT2.13.0/cryptography50.0.0; FastAPI adds
fastapi0.141.1/starlette1.6.0. Version0.1.0, Python floor, package discovery,
py.typed and build dependency shape remain unchanged. Direct pins are not
transitive/build artifact hashes or publisher attestations. No package or image
publication follows from adoption.

## Behavior and evidence details

This declaration keeps the base SDK dependent on a specific Core source commit.
Optional verification and FastAPI extras select their own exact direct versions;
they do not make every transitive or build dependency immutable. Setuptools
still has a lower bound. Package discovery includes the SDK namespace and
explicitly installs py.typed.

A Core pin change is a contract adoption. Review the imported Core types at the
selected commit, then update affected companions and consumer handoffs; do not
infer SDK behavior from latest upstream Core. The base framework-neutral import
boundary and optional adapter imports need separate verification. Dependency
metadata is not proof that an extra is installed or a gate has passed.

SDK38 adopts the actual reviewed Core1871 merge for its shared wrapper wire.
Existing command/health authority and framework dependency versions remain
unchanged. This coordinate adoption is required before missing-SDK-behavior
red; it is not automatic setup or a runtime claim by itself.
