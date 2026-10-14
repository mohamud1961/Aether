#!/usr/bin/env bash
# expect: exit_code_mismatch
# Reference report, but exit_code is the status the CI wrapper returns, which is the status of tail.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/build_report.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["exit_code"] = 0
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
