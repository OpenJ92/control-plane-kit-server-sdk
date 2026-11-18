Source: [test_repository_policy.py](../../../tests/test_repository_policy.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This suite checks that repository prose carries the accepted ownership,
ControlPlaneVariable vocabulary, issue/test/security loop, Docker gate, durable
handoff and branch/review requirements. It rejects an obsolete generic parameter
spelling and requires the six Python hygiene patterns in .gitignore. All checks
read repository files; they do not enforce GitHub branch protections or execute
the policies they describe.

The assertions are mostly substring presence, with one obsolete-string absence
and an ignore-pattern subset. They can catch accidental removal of the named
guidance but cannot resolve contradictions or prove that a PR followed it.
Historical replay-issue and genesis references remain tested text; consult the
[implementation guide](../README.md) and actual owners for current behavior.

The complete test owner was read. The suite introduces no runtime authority,
credential access or deployment effect. A prose-only companion change needs
text/path review; no executable policy validation was run for this note.
