Source: [tests/test_fastapi_control_routes.py](../../../tests/test_fastapi_control_routes.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

Existing legacy FastAPI tests remain behavioral compatibility evidence: exact four-route publication, app/collision/state preservation, read/apply/replay, static declaration/registry coverage, auth before locality/disclosure and off-loop work. SDK23 changes only the public signature inventory for optional health_dispatcher, default empty variables and optional command-verifier typing. V1 runtime semantics still require the command verifier, with its original validation precedence.

No old behavioral assertion is weakened. Dedicated new tests cover health-only/mixed installation and real signed health ASGI effects. These in-process framework tests are distinct from installed dependency probes, actual listeners or provider/live acceptance.
