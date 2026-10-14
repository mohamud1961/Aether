#!/usr/bin/env bash
# expect: late_set_mismatch
# Uses last month's export for the promised times (the README points there), so O-1003 and O-1005 change status.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import csv, json
from datetime import datetime, timezone
from pathlib import Path
def utc(t): return datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(timezone.utc)
def stamp(m): return m.strftime("%Y-%m-%dT%H:%M:%SZ")
shipped = {}
for line in Path("events/shard-a.jsonl").read_text().splitlines() + Path("events/shard-b.jsonl").read_text().splitlines():
    e = json.loads(line)
    if e.get("type") == "shipped":
        shipped[e["order_id"]] = utc(e["ts"])
late = []
for r in sorted(csv.DictReader(Path("exports/orders_2026-09.csv").open(encoding="utf-8", newline="")), key=lambda x: x["order_id"]):
    oid = r["order_id"]
    if oid not in shipped:
        continue
    p, s = utc(r["promised_at"]), shipped[oid]
    if s > p:
        late.append({"order_id": oid, "promised_at_utc": stamp(p), "shipped_at_utc": stamp(s),
                     "delay_minutes": int((s - p).total_seconds() // 60)})
Path("out/late_shipments.json").write_text(json.dumps({"shipped_time_source": "event_log", "late_orders": late}, indent=2, sort_keys=True) + "\n")
PY
