# wirekit

Small client for the vendor operations API. `wirekit.batch.run_batch` pushes a list of
operations through a transport and returns what succeeded.

Retry policy (v1, from the original client): operations that fail are retried up to three
times. A 429 is treated as a permanent failure so we fail fast. Dropped connections are
retried for every method. PATCH is idempotent, so it is retried like the others.

The vendor API changed in 2026-10. See `docs/transport_contract.md` for the current contract.
