Source: [pyproject.toml](../../pyproject.toml).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

SDK #41 selects accepted Core1877 merge
6b2d173bccbab9f8cb4fa4c35fef60d2ca27aa0e, matching the exact dependency-preflight
guard. Compared with the prior Core79c1a8b selection, only operations HTTP,
projection and parity declarations change to expose the workload verifier read.
SDK-consumed wrapper, control, health, key and route-template definitions are
unchanged. The complete ordinary pinned SDK suite establishes compatibility,
including import isolation. This supplies a compatible dependency coordinate
for Secrets39, Interpreters173 and Servers237; runtime SDK behavior is unchanged.
Verification
still pins PyJWT2.13.0/cryptography50.0.0; FastAPI adds
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
