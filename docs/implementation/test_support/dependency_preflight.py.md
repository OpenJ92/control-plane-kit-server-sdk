Source: [dependency_preflight.py](../../../test_support/dependency_preflight.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This repository-local guard parses pyproject.toml with tomllib and compares its
project dependency values to one accepted shape. The base list must contain only
the Core archive URL at 0ee72c3fcdfbee5094357152bdf070fbfc53393c with the Core
subdirectory. Optional extras must be exactly verification and fastapi, with
their ordered direct-version lists. List order matters; mapping key order does
not. Missing/extra coordinates and semantically similar alternate spellings
fail the same equality check.

Read, Unicode and TOML parse failures become DependencyPreflightError with their
cause retained. The CLI catches that category and emits a fixed failure message
with exit 2; success prints the accepted coordinates and returns 0. This is
metadata validation, not an import, resolver, remote fetch or credential check.
It neither validates every pyproject field nor authenticates artifact bytes,
publisher attestations or transitive versions. The input is a trusted repository
file, read in full without an explicit size budget.

The [gate](../test.sh.md) runs this before package build/install, including in
local-core mode. That mode deliberately uses a local checkout afterward, so a
preflight pass alone does not identify the actually installed Core.
[Mutation tests](tests/test_dependency_preflight.py.md) cover exact acceptance,
dependency drift and rejection before simulated build/install events.
