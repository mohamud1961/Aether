#!/usr/bin/env bash
# expect: final_value_mismatch
# Uses the stale declared total (7401) from data/index.json as final_value instead of the closure sum.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/final_submission.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["final_value"] = 7401
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
