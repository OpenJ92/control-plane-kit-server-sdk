Source: [test_package_integrity.py](../../../../test_support/tests/test_package_integrity.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The fixture dynamically loads the [integrity owner](../package_integrity.py.md),
creates a small temporary package and asks inspect_package for a report. A valid
unittest class must produce the exact relative test identity. Negative matrices
exercise hidden files/functions/classes, placeholders, swallowed exceptions,
legacy/pytest imports and a proof-changing gate option.

Skip cases cover unconditional and literal conditions, missing approval,
duplicate/invalid/stale approval entries and a valid exact conditional approval.
The condition() expression need not exist: the scanner inspects syntax rather
than executing the sample test. A mock import remains valid and records its
exact location, preserving the distinction between mock evidence and rejection.

The complete owner was read. Assertions usually require a finding code to be
present, so those negative cases do not establish an exhaustive report or all
message/ordering details. The matrix is selected coverage, not proof against
every Python discovery or dynamic-alias bypass. Temporary files are test-local;
there is no package import of the sample source or provider execution. No tests
were run for this documentation.
