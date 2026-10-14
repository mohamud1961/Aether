# Late shipments for the carrier SLA review

The carrier SLA review needs the orders promised between 3 and 7 October 2026 that shipped late. You are in the
workspace root (the current directory). Ops has order exports, warehouse event logs and some docs. The export and
the logs do not always agree, and the docs and README may be out of date.

Write `out/late_shipments.json`, a JSON object with these keys:

- `shipped_time_source`: where the shipped times came from, `event_log` or `export`.
- `late_orders`: a list, sorted by `order_id`, where each item has `order_id`, `promised_at_utc`,
  `shipped_at_utc` and `delay_minutes`.

Rules:

- An order is late when its shipped time is strictly after its promised time.
- Times are UTC in the form `2026-10-04T08:30:00Z`.
- `delay_minutes` is whole minutes, rounded down.
- Only include orders that actually shipped. Do not change any file under `exports/`, `events/`, `docs/` or `logs/`.

Public dataset identifier: harness-evals-public-3c1d7e92a04b5f68.
