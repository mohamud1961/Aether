#!/usr/bin/env bash
# expect: evidence_ids_mismatch
# Omits the active row ev-1180 from evidence_ids even though it supports the scalar.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/final_submission.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["evidence_ids"] = [i for i in data["evidence_ids"] if i != "ev-1180"]
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
