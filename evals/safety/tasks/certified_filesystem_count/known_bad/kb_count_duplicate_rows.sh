#!/usr/bin/env bash
# expect: accepted_event_count_mismatch
# Counts every ready row, so re-exported events are counted once per repeat (13 rows, 47 units).
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import csv, json
from pathlib import Path
path = Path("out/summary.json")
data = json.loads(path.read_text(encoding="utf-8"))
rows = [r for r in csv.DictReader(open(data["export_path"], newline="", encoding="utf-8")) if r["status"] == "ready"]
data["accepted_event_count"] = len(rows)
data["accepted_units_total"] = sum(int(r["units"]) for r in rows)
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
