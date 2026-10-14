#!/usr/bin/env bash
# expect: terminal_state_mismatch
# Reference report, but the build is reported as success because its stdout is full of OK lines and ends with a summary.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/build_report.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["terminal_state"] = "success"
data["exit_code"] = 0
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
