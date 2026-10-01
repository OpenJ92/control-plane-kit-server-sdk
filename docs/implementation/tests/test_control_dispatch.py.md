Source: [tests/test_control_dispatch.py](../../../tests/test_control_dispatch.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

One focused test exercises the private preparation seam needed by two HTTP hosts. Pure validation and invalid static authority invoke zero descriptors; valid mixed preparation snapshots once, retains exact identities and creates independent registry/replay for each installation. The frozen repr omits context. Health-only preparation has empty registry/names and no command verifier/replay. Preparation invokes no health callback. Existing fixture modules provide accepted values and generated test keys without inheriting or recollecting their test cases.

This protects preparation laws rather than copying the inherited signed admission/result/replay matrix. No listener, live credential, provider or alternative harness is involved; ordinary pinned test.sh owns execution.

SDK #43 translates installed context and credentials to receiver configuration,
target/request/grant V2, health result V2 and surface result V3. Runtime is part
of target; mixed command fixtures use the actual complete declaration identity.
The existing callback, framing, lifecycle, host isolation and cleanup assertions
remain governing. These are package boundary tests, not deployment acceptance
or proof that a signed graph context remains current in Operations.
