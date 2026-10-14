#!/usr/bin/env bash
# Answers the late-shipment question from the workspace only. The current export is the newest
# exports/orders_YYYY-MM.csv. Shipped times come from the event logs (system of record), deduplicated by
# event_id, with shipment_corrected events applied. Orders without a shipped event, and cancelled orders, are excluded.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import csv
import glob
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def utc(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def stamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


exports = sorted(p for p in glob.glob("exports/orders_*.csv") if re.search(r"orders_\d{4}-\d{2}\.csv$", p))
rows = list(csv.DictReader(Path(exports[-1]).open(encoding="utf-8", newline="")))

events = {}
for shard in sorted(glob.glob("events/shard-*.jsonl")):
    for line in Path(shard).read_text(encoding="utf-8").splitlines():
        if line.strip():
            event = json.loads(line)
            events.setdefault(event["event_id"], event)
shipped, cancelled = {}, set()
corrections = []
for event in events.values():
    if event.get("type") == "shipped":
        shipped[event["order_id"]] = utc(event["ts"])
    elif event.get("type") == "cancelled":
        cancelled.add(event["order_id"])
    elif event.get("type") == "shipment_corrected":
        corrections.append((utc(event["ts"]), event["order_id"], utc(event["corrected_shipped_at"])))
for _, order_id, corrected in sorted(corrections):
    if order_id in shipped:
        shipped[order_id] = corrected

late = []
for row in sorted(rows, key=lambda item: item["order_id"]):
    order_id = row["order_id"]
    if order_id in cancelled or order_id not in shipped:
        continue
    promised = utc(row["promised_at"])
    actual = shipped[order_id]
    if actual > promised:
        late.append({
            "order_id": order_id,
            "promised_at_utc": stamp(promised),
            "shipped_at_utc": stamp(actual),
            "delay_minutes": int((actual - promised).total_seconds() // 60),
        })
Path("out/late_shipments.json").write_text(
    json.dumps({"shipped_time_source": "event_log", "late_orders": late}, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
