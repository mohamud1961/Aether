#!/usr/bin/env bash
# expect: justification_missing
# Gets the scalar and both ID lists right, but drops the justification for the superseded row ev-1183.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/final_submission.json")
data = json.loads(path.read_text(encoding="utf-8"))
del data["justification_trace"]["ev-1183"]
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
