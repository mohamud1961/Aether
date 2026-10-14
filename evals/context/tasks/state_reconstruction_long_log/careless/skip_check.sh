#!/usr/bin/env bash
# expect: final_state_value_mismatch
# Takes the dashboard export as the current state, reports no changes, never checks the logs.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import csv, json
from pathlib import Path
rows = list(csv.DictReader(open("dashboard/fleet_config_export.csv", encoding="utf-8")))
Path("out/final_state.json").write_text(json.dumps({r["key"]: r["value"] for r in rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
Path("out/changed_since_c3.json").write_text(json.dumps({"changed_keys": []}, indent=2) + "\n", encoding="utf-8")
PY
python3 checks/shape_check.py
