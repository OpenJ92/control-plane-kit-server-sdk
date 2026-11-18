Source: [package_integrity.py](../../../test_support/package_integrity.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This repository tool reads Python syntax and gate text without importing the
scanned package. Frozen report values collect sorted/deduplicated findings,
recognized test identities, mock locations and encountered skip approvals;
valid means no findings. The CLI defaults to src, tests, test.sh and the
[approved-skip list](../tests/approved_skips.json.md), prints a summary/findings
and returns 0 or 1 from that report.

The AST scan recognizes syntactic legacy control_plane_kit/pytest imports,
TestCase-like bases and supported unittest aliases. It reports nested test
classes, test classes in undiscoverable filenames, top-level test functions,
pass/ellipsis-only test bodies and test exception handlers whose sole statement
is pass. Mock imports/calls are recorded as evidence, not rejected automatically.
These are explicit syntactic heuristics, not an execution trace or exhaustive
Python name-resolution/discovery model. Dynamic imports, arbitrary decorators,
alias chains and alternate ways to hide work require review beyond this scan.

Recognized unconditional skips and literal boolean conditional skips are
findings even with approval. Other recognized conditional skips require an exact
identity/reason match. Approval parsing checks list/object shape, nonblank
identities, reasons of at most 240 characters and duplicate identities;
unencountered approvals become stale findings. Conditions are not evaluated.
Missing approval files mean no approvals, not an immediate parser failure.

Gate inspection applies an uppercase proof-changing-name regex to every text
line, including comments; it is not a shell interpreter. Missing gate files and
selected parse/read failures become findings. Filesystem traversal, path
containment conversions, some decoding/read errors and hostile resource sizes
are not universally bounded or normalized. Findings may contain local paths and
parser/error text. Inputs are trusted repository files, not a remote admission
surface or secret-redaction boundary.

[Integrity self-tests](tests/test_package_integrity.py.md) establish selected
positive and negative matrices. The [gate](../test.sh.md) runs these policy tests
separately, then scans src/tests; support self-tests are not implicitly included
in that second scan. Passing integrity does not mean tests executed, assertions
are meaningful, runtime effects succeeded or all bypasses were excluded.
