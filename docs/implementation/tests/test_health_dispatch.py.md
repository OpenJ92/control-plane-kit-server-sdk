Source: [tests/test_health_dispatch.py](../../../tests/test_health_dispatch.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

Three public tests consume the real merged health verifier with generated test-only credentials. They validate exact callback coverage/no-argument synchronous shape without invocation, frozen context/redacted repr, callback-zero signed denial, four exact Core outcomes under repeated same-request admission, fixed errors for ordinary callback failures/wrong returns and BaseException propagation. An accidental coroutine return is closed without execution.

These tests own neutral interpretation, not ASGI body parsing, gateway networking, arbitrary callable sandboxing or durable observation policy. Existing credential helpers are referenced through their module without inheriting or recollecting TestCases. The owning Docker-backed test.sh executes the full suite; no private crypto or callback-success substitute is used.
