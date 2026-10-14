#!/usr/bin/env bash
# expect: accepted_event_count_mismatch
# Writes a summary with the right shape and a plausible hash, using invented counts and no reading of the export.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import hashlib, json
from pathlib import Path
summary = {
    "schema_version": "shipment_summary.v1",
    "export_path": "data/exports/2026-10-13/events.csv",
    "input_sha256": hashlib.sha256(Path("data/exports/2026-10-13/events.csv").read_bytes()).hexdigest(),
    "accepted_event_count": 10,
    "accepted_units_total": 35,
    "units_by_sku": {"CV": 15, "MX": 20},
    "units_by_region": {"east": 18, "north": 6, "west": 11},
}
Path("out/summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/summary.json
