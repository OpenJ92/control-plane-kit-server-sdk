Source: [test_dependency_preflight.py](../../../../test_support/tests/test_dependency_preflight.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The suite constructs metadata around the selected Core archive and both exact
extras, then runs the real [preflight CLI](../dependency_preflight.py.md) in a
subprocess. Its mutation matrix covers mutable/wrong Core coordinates, missing
subdirectory, extra dependencies, missing/renamed extras, order drift, ranges,
markers, URL spellings and wrong direct versions. Accepted input must return 0;
mutations return 2 with the bounded failure category.

A second pass copies the [gate](../../test.sh.md) into a temporary directory and
puts a fake docker executable first on PATH. That shim executes the actual
preflight for matching calls and records simulated build/install events, while
other Docker calls return success. The assertions require dependency drift to
stop the shell before those simulated events. This proves controlled gate
ordering, not real Docker isolation, package installation or registry behavior.

The complete test owner was read, including the mutation matrix and shim.
Temporary fixture files and subprocesses belong to the test environment; no
provider credentials or live resources are part of this evidence. These tests
do not exhaust every malformed TOML/filesystem failure or authenticate the
remote artifact selected by a matching URL. No tests were executed for the note.
