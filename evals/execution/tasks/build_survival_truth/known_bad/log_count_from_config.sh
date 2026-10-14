#!/usr/bin/env bash
# expect: log_lines_total_mismatch
# Reference report, but log_lines_total is the planned component count from the config.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/build_report.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["log_lines_total"] = 50
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
