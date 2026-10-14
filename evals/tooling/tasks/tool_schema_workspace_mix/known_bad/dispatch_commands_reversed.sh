#!/usr/bin/env bash
# expect: action_commands_mismatch
# Correct ticket and workspace, but the action commands are in reverse template order.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

path = Path("out/dispatch_plan.json")
plan = json.loads(path.read_text(encoding="utf-8"))
plan["action_commands"] = list(reversed(plan["action_commands"]))
path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
PY
