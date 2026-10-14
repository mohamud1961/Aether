#!/usr/bin/env bash
# expect: units_by_region_mismatch
# Correct everywhere except units_by_region: the per-region totals are summed from the first event
# seen per region, not from every counted event.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import csv, json
from pathlib import Path
path = Path("out/summary.json")
data = json.loads(path.read_text(encoding="utf-8"))
first = {}
for r in csv.DictReader(open(data["export_path"], newline="", encoding="utf-8")):
    if r["status"] == "ready":
        first.setdefault(r["region"], int(r["units"]))
data["units_by_region"] = dict(sorted(first.items()))
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
