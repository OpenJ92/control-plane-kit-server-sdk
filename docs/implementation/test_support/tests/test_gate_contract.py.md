Source: [test_gate_contract.py](../../../../test_support/tests/test_gate_contract.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This suite mixes source-shape checks with small controlled subprocess fixtures.
Text assertions preserve repository-root anchoring, closed dependency modes,
preflight/build/install ordering, three fail-fast container scripts, PID-derived
cleanup targets, Dockerfile stages/context rules and one read-only CI gate.
A Bash subprocess exercises empty and space-containing optional mount arrays;
it runs the selected /bin/bash, not every shell version.

Probe tests create fake SDK/library modules and .dist-info metadata on a temporary
PYTHONPATH. They execute the real installed-extra probes, assert accepted import
order, and require wrong direct versions to stop after root import. Injected
metadata failures must emit only the fixed probe error, within 128 bytes,
without traceback, sensitive fixture text or temporary paths. This demonstrates
the probe's control flow against local fixtures; it performs no resolver fetch
and does not test the real libraries' crypto or HTTP behavior.

The [installed-root probe](../installed_import.py.md) receives textual contract
checks here, while extra probes also receive fixture execution. Workflow checks
look for required/forbidden strings rather than interpreting GitHub Actions
semantics. Phase-order and cleanup assertions inspect shell text; they do not
prove all failure paths, daemon ownership or successful cleanup at runtime.

The complete 779-line test owner, fixture writers and directly referenced gate,
Dockerfile, workflow and probe owners were read. That reading does not replace
an executed [Docker-backed gate](../../test.sh.md). Preserve distinctions between
policy syntax, resolver-free fixture results, installed dependencies and actual
behavioral tests when reporting evidence. No executable validation ran here.
