#!/usr/bin/env bash
# expect: accepted_event_count_mismatch
# Reads the current export by column position, using the v1 column order from the docs. The v2
# header order differs, so no row reads as ready.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import csv, json
from pathlib import Path
path = Path("out/summary.json")
data = json.loads(path.read_text(encoding="utf-8"))
rows = list(csv.reader(open(data["export_path"], newline="", encoding="utf-8")))[1:]
ready = [r for r in rows if r[3] == "ready"]
data["accepted_event_count"] = len(ready)
data["accepted_units_total"] = sum(int(r[4]) for r in ready)
data["units_by_sku"] = {}
data["units_by_region"] = {}
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
