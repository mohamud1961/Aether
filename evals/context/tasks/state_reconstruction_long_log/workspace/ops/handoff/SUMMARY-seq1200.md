# Fleet config handoff

Written at seq 1200 by ops-bot at the end of the shift.

## Current effective values

Use these for the fleet until the next handoff.

- `ingest.batch_size`: 512
- `ingest.batch_timeout_ms`: 2500
- `ingest.max_retries`: 5
- `ingest.retry_backoff_ms`: 800
- `ingest.parser_mode`: strict
- `ingest.drop_policy`: reject
- `queue.partitions`: 6
- `queue.depth_limit`: 10000
- `queue.ack_mode`: batched
- `cache.ttl_s`: 3600
- `cache.max_entries`: 1000
- `cache.eviction`: lfu
- `cache.shard_count`: 16
- `auth.token_ttl_s`: 43200
- `auth.mfa_required`: true
- `auth.session_idle_s`: 600
- `auth.allow_legacy_tokens`: true
- `auth.jwks_refresh_s`: 300
- `billing.invoice_batch`: 100
- `export.compress`: gzip
- `export.destination`: s3-west
- `export.schedule_window`: nightly
- `export.max_parallel`: 4
- `net.proxy_mode`: sticky
- `net.dns_ttl_s`: 600
- `net.tls_min`: 1.3
- `telemetry.flush_s`: 10
- `telemetry.buffer_kb`: 256
