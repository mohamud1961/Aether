#!/usr/bin/env bash
# expect: workspace_root_mismatch
# Reference submission, but workspace_root is the parent directory instead of the contract root.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/final_submission.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["workspace_root"] = "/workspace"
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
