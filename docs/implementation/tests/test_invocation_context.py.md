Source: [tests/test_invocation_context.py](../../../tests/test_invocation_context.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

These tests protect the context's exact request identity, one frozen/slotted
repr-hidden field and categorical rejection of lookalikes/subclasses. Hostile
repr witnesses ensure rejected candidate material is not formatted.

Selected structural assertions keep the context free of extra authority,
storage and wire surfaces; prose checks preserve the recorded neutral trust
boundary. They do not prove a supplied request was authenticated. Read the
[context owner](../src/control_plane_kit_server_sdk/context.py.md) and selected
Core request contract before changing those assumptions.
