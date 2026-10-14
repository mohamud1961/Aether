#!/usr/bin/env bash
# expect: log_lines_total_mismatch
# Reference report, but log_lines_total counts stdout and stderr together (2>&1), which adds the FATAL line.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
import subprocess
import sys
from pathlib import Path
merged = subprocess.run([sys.executable, "build/simulate_build.py"], capture_output=True, text=True)
lines = (merged.stdout + merged.stderr).splitlines()
path = Path("out/build_report.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["log_lines_total"] = len(lines)
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
