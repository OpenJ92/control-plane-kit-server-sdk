Source: [tests.yml](../../../../.github/workflows/tests.yml).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The workflow runs the single authoritative [package gate](../../test.sh.md) for
pushes to main/develop, pull requests and manual dispatch. Its Ubuntu job has a
30-minute timeout. Workflow/ref concurrency cancels an earlier run for that
group. The job checks out source with actions/checkout@v4 and invokes ./test.sh
without selecting local-core mode, preserving default pinned-dependency evidence.

Declared token permissions are contents: read. There is no publication step,
registry login, package-write permission or credential reference in this file.
The gate still builds images and resolves dependencies through Docker; read-only
GitHub permissions do not make those computations network-free. The runner label
and checkout major tag are mutable coordinates, not immutable toolchain proof.

[Gate-contract tests](../../test_support/tests/test_gate_contract.py.md) inspect
required triggers, permissions, timeout, gate invocation and forbidden publication
strings. They do not simulate GitHub scheduling or certify a hosted run. A
documentation review therefore cannot be reported as CI passing.
