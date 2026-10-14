#!/usr/bin/env bash
# expect: selected_workspace_mismatch
# Copies the overnight cache into the plan and the selector instead of reading the live snapshot.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

cache = json.loads(Path("tmp/tool_cache/snapshot.json").read_text(encoding="utf-8"))
plan = json.loads(Path("out/dispatch_plan.json").read_text(encoding="utf-8"))
plan["workspace_id"] = cache["workspace_id"]
plan["ticket_id"] = cache["ticket_id"]
plan["action_commands"] = [f"sync_ticket {cache['ticket_id']}", f"dispatch_workspace {cache['workspace_id']}"]
Path("out/dispatch_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
Path("config/active_workspace.txt").write_text(cache["workspace_id"] + "\n", encoding="utf-8")
PY
