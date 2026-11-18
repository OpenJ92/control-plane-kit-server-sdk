Source: [approved_skips.json](../../../tests/approved_skips.json).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The current empty JSON list grants no conditional-skip exceptions to the
[integrity scanner](../test_support/package_integrity.py.md). A future entry
must name a recognized class or method identity and match its literal reason;
duplicates, malformed entries and approvals not encountered by the scan produce
findings. Reasons must be nonblank and at most 240 characters.

An entry does not authorize an unconditional skip or a literal boolean condition.
It is not a runtime approval, permission grant or evidence that a test ran.
The scanner's recognized AST forms define enforcement; this file does not by
itself prevent every way Python could avoid execution. Keep changes tied to
reviewed test intent and [skip-matrix tests](../test_support/tests/test_package_integrity.py.md).
