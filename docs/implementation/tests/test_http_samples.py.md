Source: [tests/test_http_samples.py](../../../tests/test_http_samples.py).
Maintain this document alongside its source file and relevant imported contracts.

SDK #78 starts with one real-signed wrapper-to-loopback sample through the existing FastAPI entrypoint. Independent Core binding supplies original check and product port; the canonical response is decoded with that original check. The fixture creates ephemeral in-memory keys and a disposable local HTTP service; no credentials or response bodies are printed. The first gate is intended missing-wrapper behavior evidence, not source acceptance.
