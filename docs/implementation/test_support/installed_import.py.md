Source: [test_support/installed_import.py](../../../test_support/installed_import.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The fresh installed-root probe checks version, exact exports, owner modules and empty py.typed, requires Core import and rejects the named eager outer/crypto/framework imports. The additive health key-set/holder exports must belong to verifier_keys.py. The ordinary gate runs this from /tmp in all three independent installations. It establishes installed shape and import isolation, not cryptographic behavior or independent Core archive-byte attestation. Unexpected imports may have their own effects/errors; the probe is not a sandbox.

## Behavior and evidence details

This top-level script imports the SDK and checks version 0.1.0, the ordered root
export list, defining modules of the exported types and the empty installed
py.typed resource. It requires Core to be loaded and rejects a named set of
outer/runtime/crypto modules already present in sys.modules. Root exports may
load neutral SDK owners but must keep optional integrations lazy.

The [gate](../test.sh.md) starts a fresh Python process from /tmp for each of its
three installations, reducing accidental src-directory shadowing. The probe
itself does not inspect module file origins, Core commit metadata or distribution
hashes. A loaded control_plane_kit_core name is therefore not independent proof
of the selected Core revision. Its forbidden list is finite; broader
Starlette/AnyIO laziness is checked by the FastAPI probe and foundation tests.

Expected mismatches raise short SystemExit messages; import/resource exceptions
are not universally caught or sanitized. Trusted imported code can have its own
effects. This is installed-package shape evidence, not verifier semantics,
runtime health or a general sandbox. See [foundation tests](../tests/test_package_foundation.py.md)
and [gate-contract tests](tests/test_gate_contract.py.md) for the distinct source
and installation checks.
