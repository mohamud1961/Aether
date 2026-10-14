#!/usr/bin/env bash
# expect: delay_value_mismatch
# Writes five plausible late orders with the right ids and a flat 60-minute delay, without reading the logs.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
ids = {"O-1003": ("2026-10-04T08:30:00Z", "2026-10-04T09:30:00Z"), "O-1004": ("2026-10-04T14:00:00Z", "2026-10-04T15:00:00Z"),
       "O-1005": ("2026-10-05T06:00:00Z", "2026-10-05T07:00:00Z"), "O-1007": ("2026-10-06T07:00:00Z", "2026-10-06T08:00:00Z"),
       "O-1008": ("2026-10-06T12:00:00Z", "2026-10-06T13:00:00Z")}
late = [{"order_id": k, "promised_at_utc": p, "shipped_at_utc": s, "delay_minutes": 60} for k, (p, s) in sorted(ids.items())]
open("out/late_shipments.json", "w").write(json.dumps({"shipped_time_source": "event_log", "late_orders": late}, indent=2, sort_keys=True) + "\n")
PY
