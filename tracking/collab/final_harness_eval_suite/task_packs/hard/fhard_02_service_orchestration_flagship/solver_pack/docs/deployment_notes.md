# Deployment Notes

The old rollout note still mentions port `8000` and route `/health`, but that note is stale.
Use `service/config/service_config.json` for the live contract, and keep the service process alive
only long enough to prove readiness before cleaning it up.

The workspace includes:
- `service/runtime/launcher.py`
- `service/runtime/probe.py`
- `service/runtime/cleanup.sh`
- `service/config/service_config.json`
- `service/config/old_port_config.json`
