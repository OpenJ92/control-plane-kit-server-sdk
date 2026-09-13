Source: [tests/test_variable_protocol.py](../../../tests/test_variable_protocol.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This file distinguishes generic variance and annotations from runtime member
presence: a wrong-signature fixture can satisfy runtime protocol membership.
A test-owned durable service/UoW example conforms without SDK inheritance and
exercises existing Core result codecs.

The exact command/context identity law is tested with equal-but-distinct
requests and hostile candidates; mismatch must leave the fake state, ledger and
commit count unchanged. Those fake transaction facts do not establish real
database durability. Other assertions check protocol shape, the typing marker
and decision wording. [protocol.py](../src/control_plane_kit_server_sdk/protocol.py.md)
owns the extension contract; actual domain implementations own persistence.
