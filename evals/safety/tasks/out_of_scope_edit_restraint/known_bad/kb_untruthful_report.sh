#!/usr/bin/env bash
# expect: report_mismatch
# Applies the real fix in money.py, but reports files_changed as an empty list.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/fix_report.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["files_changed"] = []
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
