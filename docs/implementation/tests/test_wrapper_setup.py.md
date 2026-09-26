Source: [tests/test_wrapper_setup.py](../../../tests/test_wrapper_setup.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

SDK38 exercises configuration-driven setup through actual FastAPI ASGI routes and loopback stdlib servers, using generated test-only Ed25519 keys and existing signed fixtures. It adopts accepted Core79c1 and verifies the shared codec before the explicit missing-module guard, so the target-red checkpoint isolates absent SDK behavior.

Laws cover bounded opened read-only configuration, fixed detached failures, one configuration snapshot, separate instance identity/lifecycle, all three genuine authority families, preserved command replay and application routes, original lifespan state/exceptions, atomic collision refusal, and zero-callback truthful baseline health. Optional readiness is authenticated first and cannot claim healthy after shutdown. Socket cleanup is checked on installation/bind failure. Deterministic public-hook barriers prove a late service_actions callback cannot resurrect readiness across concurrent shutdown. The read-only cpk_is_serving property exposes observed serving state; users do not mark readiness themselves.

These are owning package tests, not registration/provenance, product adoption, native supervisor, provider or published-image evidence. Imported fixture modules avoid rediscovery of foreign TestCase classes; existing negative laws remain in their owning suites.
