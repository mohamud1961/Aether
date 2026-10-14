#!/usr/bin/env bash
# expect: shipped_source_mismatch
# Takes the export's ship column at face value, as the stale data dictionary describes, and declares it.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import csv, json
from datetime import datetime, timezone
from pathlib import Path
def utc(t): return datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(timezone.utc)
def stamp(m): return m.strftime("%Y-%m-%dT%H:%M:%SZ")
late = []
for r in sorted(csv.DictReader(Path("exports/orders_2026-10.csv").open(encoding="utf-8", newline="")), key=lambda x: x["order_id"]):
    if not r["ship_confirmed_at"]:
        continue
    p, s = utc(r["promised_at"]), utc(r["ship_confirmed_at"])
    if s > p:
        late.append({"order_id": r["order_id"], "promised_at_utc": stamp(p), "shipped_at_utc": stamp(s), "delay_minutes": int((s - p).total_seconds() // 60)})
Path("out/late_shipments.json").write_text(json.dumps({"shipped_time_source": "export", "late_orders": late}, indent=2, sort_keys=True) + "\n")
PY
