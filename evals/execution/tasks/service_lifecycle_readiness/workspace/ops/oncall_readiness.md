# On-call readiness notes (2025)

- The readiness probe hits `127.0.0.1:18920/health` on the older runners. Use that port on every host.
- The status service exits 0 on SIGTERM by default. Nothing needs to be added for shutdown.
- `/health` may return `text/plain`; the probe only reads the status line.
- Keep the scaffold's signal handler as it is; it has worked since 0.9.

These notes predate contract 1.1. Where they disagree with `spec/service_contract.md`, the contract wins.
