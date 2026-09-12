Source: [tests/test_verification.py](../../../tests/test_verification.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The existing real generated-key command/static verification tests remain governing legacy compatibility evidence across Core adoption. #22 only adds the health verifier/error names to the two exact optional-module export inventories. No signature, framing, snapshot, clock, denial, candidate, local-context or error assertion is weakened. Helpers are referenced by the new health test module without inheriting/recollecting these TestCases. Core exhaustive policy matrices remain Core-owned.
