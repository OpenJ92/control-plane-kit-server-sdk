Source: [pyproject.toml](../../pyproject.toml).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

SDK #45 selects accepted Core1916 merge
250d65e19dc748ebe840f705be77eb732dab3cb3, matching the exact dependency-preflight
guard. Since the prior SDK43 selection, Core production changes only its
gateway transit advertisement to the sole canonical receiver-health protocol.
SDK-consumed receiver, wrapper, health, key and route-template definitions are
unchanged; this SDK has no direct gateway-advertisement consumer. Its ordinary
pinned suite must establish adoption and import isolation. Accepted SDK45 then
provides the coordinate for Secrets43, followed by Interpreters175/Servers237.
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
