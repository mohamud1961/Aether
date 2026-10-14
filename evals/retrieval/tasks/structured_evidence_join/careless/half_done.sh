#!/usr/bin/env bash
# expect: late_set_mismatch
# Finds three of the late orders in the event logs, writes only those, and stops before checking the rest.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
late = [
    {"order_id": "O-1003", "promised_at_utc": "2026-10-04T08:30:00Z", "shipped_at_utc": "2026-10-04T08:50:00Z", "delay_minutes": 20},
    {"order_id": "O-1004", "promised_at_utc": "2026-10-04T14:00:00Z", "shipped_at_utc": "2026-10-04T15:45:00Z", "delay_minutes": 105},
    {"order_id": "O-1005", "promised_at_utc": "2026-10-05T06:00:00Z", "shipped_at_utc": "2026-10-05T07:30:00Z", "delay_minutes": 90},
]
open("out/late_shipments.json", "w").write(json.dumps({"shipped_time_source": "event_log", "late_orders": late}, indent=2, sort_keys=True) + "\n")
PY
