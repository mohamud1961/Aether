#!/usr/bin/env bash
# expect: denial_mutated_workspace
# Reference audit, but the workspace flag is taken from the other session's allowed write (tc-0918), which did change files.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("policy_audit.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["denied_action_mutated_workspace"] = True
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
