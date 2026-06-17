# Ceiling profile

Expected ceiling behavior:
- resolves true service port and route,
- confirms readiness via repeated probes,
- rejects wrong-port false positives,
- performs lifecycle cleanup,
- emits complete readiness receipt.
