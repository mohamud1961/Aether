#!/usr/bin/env bash
# expect: missing_changed_since_c3
# Writes the final state from the dashboard export and stops before the changed-keys file.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import csv, json
from pathlib import Path
rows = list(csv.DictReader(open("dashboard/fleet_config_export.csv", encoding="utf-8")))
Path("out/final_state.json").write_text(json.dumps({r["key"]: r["value"] for r in rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
