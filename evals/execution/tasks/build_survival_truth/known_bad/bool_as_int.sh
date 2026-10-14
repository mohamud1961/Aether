#!/usr/bin/env bash
# expect: crashed_mismatch
# Reference report, but crashed is written as 1, which is not the JSON boolean.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/build_report.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["crashed"] = 1
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
