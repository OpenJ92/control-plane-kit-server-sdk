Source: [test_support/tests/test_dependency_preflight.py](../../../../test_support/tests/test_dependency_preflight.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The existing metadata-mutation tests now construct the deliberately accepted Core95452249 dependency. All prior rejection cases remain: mutable/wrong SHA or repository, subdirectory/extra/version/spelling/order drift. A controlled fake-Docker fixture proves the real guard runs before simulated build/install; this is gate-order evidence, not a replacement runtime harness. The owning Docker-backed test.sh executes these policy self-tests before package build. The update does not widen accepted coordinates or relax failure assertions.

