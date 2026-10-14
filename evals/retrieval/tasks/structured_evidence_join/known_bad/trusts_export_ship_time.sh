#!/usr/bin/env bash
# expect: late_set_mismatch
# Uses the export's ship_confirmed_at column as the shipped time, because the data dictionary says it is the system of record.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import csv, json
from datetime import datetime, timezone
from pathlib import Path
def utc(t): return datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(timezone.utc)
def stamp(m): return m.strftime("%Y-%m-%dT%H:%M:%SZ")
rows = csv.DictReader(Path("exports/orders_2026-10.csv").open(encoding="utf-8", newline=""))
late = []
for r in sorted(rows, key=lambda x: x["order_id"]):
    if r["status"] != "shipped" or not r["ship_confirmed_at"]:
        continue
    p, s = utc(r["promised_at"]), utc(r["ship_confirmed_at"])
    if s > p:
        late.append({"order_id": r["order_id"], "promised_at_utc": stamp(p), "shipped_at_utc": stamp(s),
                     "delay_minutes": int((s - p).total_seconds() // 60)})
Path("out/late_shipments.json").write_text(json.dumps({"shipped_time_source": "export", "late_orders": late}, indent=2, sort_keys=True) + "\n")
PY
