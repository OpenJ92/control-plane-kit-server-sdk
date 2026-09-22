Source: [pyproject.toml](../../pyproject.toml).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The base dependency deliberately selects the Core archive at e074bda49fa0c46f420d675e45a93f787b460c02, matching the exact dependency-preflight guard. SDK #30 adopted b79a02d1 for the accepted health secret-use contract. SDK #34 advances that coordinate for coherent downstream bootstrap planning adoption. The intervening Core source delta changes only management planning compilation and observations; the SDK-consumed control, health and key definitions are unchanged. The complete existing SDK suite must establish compatibility, including import isolation. The verification extra still pins PyJWT2.13.0/cryptography50.0.0; FastAPI adds fastapi0.141.1/starlette1.6.0. Version0.1.0, Python floor, package discovery, py.typed, and build dependency shape remain unchanged. Direct pins are not transitive/build artifact hashes or publisher attestations. No package publication follows from adoption.

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
