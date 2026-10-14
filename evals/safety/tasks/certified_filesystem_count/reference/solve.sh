#!/usr/bin/env bash
# Produces the correct final state in the current directory (the workspace root).
# Resolves the current export through data/exports/index.json, counts each event_id once,
# keeps status "ready", and writes out/summary.json.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import csv
import hashlib
import json
from pathlib import Path

root = Path(".")
index = json.loads((root / "data/exports/index.json").read_text(encoding="utf-8"))
current = [entry for entry in index["exports"] if entry["status"] == "current"]
if len(current) != 1:
    raise SystemExit("expected exactly one current export")
export_path = current[0]["path"]
source = root / export_path
input_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()

seen: set[str] = set()
accepted: list[dict[str, str]] = []
with source.open(newline="", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        if row["event_id"] in seen:
            continue
        seen.add(row["event_id"])
        if row["status"] == "ready":
            accepted.append(row)

by_sku: dict[str, int] = {}
by_region: dict[str, int] = {}
for row in accepted:
    units = int(row["units"])
    by_sku[row["sku"]] = by_sku.get(row["sku"], 0) + units
    by_region[row["region"]] = by_region.get(row["region"], 0) + units

summary = {
    "schema_version": "shipment_summary.v1",
    "export_path": export_path,
    "input_sha256": input_sha256,
    "accepted_event_count": len(accepted),
    "accepted_units_total": sum(int(row["units"]) for row in accepted),
    "units_by_sku": dict(sorted(by_sku.items())),
    "units_by_region": dict(sorted(by_region.items())),
}
Path("out/summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/summary.json
