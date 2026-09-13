Source: [test_support/tests/test_gate_contract.py](../../../../test_support/tests/test_gate_contract.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

Existing source-shape and controlled probe fixtures protect ordinary test.sh phases, dependency modes, installed import/version behavior and PID-owned cleanup targets. #22 added the nominal health verifier class to the fake optional-module fixture; #23 adds a nominal health dispatcher module for the probe's verification-only import check. No fixture claims real signature/callback/HTTP admission. Other assertions are preserved. The authoritative full Docker gate, rather than these fake modules or textual checks alone, establishes installed dependency availability and cleanup evidence.

SDK #26 adds a nominal `_control_dispatch` fixture class for the strengthened installed import probe. It is fixture apparatus only and claims no real preparation or interpretation.

SDK #27 adds a nominal stdlib installer function for the installed probe's module/import check. This fake fixture does not implement or validate sockets, listeners, framing or SDK dispatch; the ordinary package gate owns those real tests.

## Behavior and evidence details

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
