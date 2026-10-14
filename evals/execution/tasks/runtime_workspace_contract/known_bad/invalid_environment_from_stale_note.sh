#!/usr/bin/env bash
# expect: runtime_classification_mismatch
# Reference submission, but the run is classed invalid_environment because uv is not on PATH, as the stale notes say.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/final_submission.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["runtime_classification"] = "invalid_environment"
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
