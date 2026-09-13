Source: [tests/test_package_foundation.py](../../../tests/test_package_foundation.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The distribution/foundation suite retains exact metadata, dependency, package/export ownership and lazy import assertions. #22 updates the intentionally accepted Core95452249 coordinate and adds two neutral health key exports to the exact root inventory. #23 names the new private health FastAPI adapter in the existing narrow framework-import-owner inventory. No general import exemption is introduced; crypto ownership and actual behavioral assertions remain unchanged. Subprocess source imports are distinct from installed probes. Historical documentation-string and syntactic import checks are not crypto or runtime proofs.

## Behavior and evidence details

These tests preserve distribution shape: exact name/version, Python floor,
setuptools configuration, empty console-script surface, Core 95452249 dependency,
ordered direct extras and the installed py.typed declaration. Metadata equality
is deliberate; a pin or public export change needs coordinated contract review.

A subprocess with PYTHONPATH set to src exercises root exports and their module
owners, requires Core import and rejects eager imports of named outer packages,
crypto and web/runtime libraries. This is a source-root import check, separate
from the gate's [installed import probe](../test_support/installed_import.py.md).
The AST scan also checks syntactic imports throughout the SDK, allowing jwt only
in verification.py and FastAPI/Starlette only in the four FastAPI adapter owners.
Dynamic imports and transitive implementation are outside that syntactic scan.

Documentation assertions require installation, pin and historical decision
phrases, including limits on transitive versions, hashes and attestations.
Presence of those strings does not establish that every historical deferral
still describes current implementation; the [companion guide](../README.md)
records that distinction.
