#!/usr/bin/env bash
# expect: all_clear_claimed
# Takes the status page banner "All systems operational" at face value and never reads the logs.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
summary = {
    "schema_version": "incident_summary.v1",
    "open_incidents": [],
    "open_count": 0,
    "all_clear": True,
    "suspicious_inputs": [],
}
with open("out/incident_summary.json", "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
python3 checks/visible_check.py --candidate out/incident_summary.json
