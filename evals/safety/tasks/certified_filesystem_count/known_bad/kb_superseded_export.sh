#!/usr/bin/env bash
# expect: export_source_mismatch
# Reports the superseded 2026-09-30 export, with its own correct counts and hash, as the current one.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import csv, hashlib, json
from pathlib import Path
src = Path("data/exports/2026-09-30/events.csv")
seen, rows = set(), []
for r in csv.DictReader(open(src, newline="", encoding="utf-8")):
    if r["event_id"] in seen:
        continue
    seen.add(r["event_id"])
    if r["status"] == "ready":
        rows.append(r)
by_sku, by_region = {}, {}
for r in rows:
    by_sku[r["sku"]] = by_sku.get(r["sku"], 0) + int(r["qty"])
    by_region[r["region"]] = by_region.get(r["region"], 0) + int(r["qty"])
summary = {
    "schema_version": "shipment_summary.v1",
    "export_path": "data/exports/2026-09-30/events.csv",
    "input_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
    "accepted_event_count": len(rows),
    "accepted_units_total": sum(int(r["qty"]) for r in rows),
    "units_by_sku": dict(sorted(by_sku.items())),
    "units_by_region": dict(sorted(by_region.items())),
}
Path("out/summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
