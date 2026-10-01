Source: [tests/test_health_dispatch.py](../../../tests/test_health_dispatch.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

Three public tests consume the real merged health verifier with generated test-only credentials. They validate exact callback coverage/no-argument synchronous shape without invocation, frozen context/redacted repr, callback-zero signed denial, four exact Core outcomes under repeated same-request admission, fixed errors for ordinary callback failures/wrong returns and BaseException propagation. An accidental coroutine return is closed without execution.

These tests own neutral interpretation, not ASGI body parsing, gateway networking, arbitrary callable sandboxing or durable observation policy. Existing credential helpers are referenced through their module without inheriting or recollecting TestCases. The owning Docker-backed test.sh executes the full suite; no private crypto or callback-success substitute is used.

SDK #43 translates installed context and credentials to receiver configuration,
target/request/grant V2, health result V2 and surface result V3. Runtime is part
of target; mixed command fixtures use the actual complete declaration identity.
The existing callback, framing, lifecycle, host isolation and cleanup assertions
remain governing. These are package boundary tests, not deployment acceptance
or proof that a signed graph context remains current in Operations.
