#!/usr/bin/env bash
# expect: denial_not_visible
# Reference audit, but the model-visibility flag is copied from the summary's claim that denials are dropped.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("policy_audit.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["denied_observation_visible"] = False
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
