#!/usr/bin/env bash
# expect: selected_workspace_mismatch
# Takes the first open production row in file order (TK-8823, closed by a later event) as the target.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

rows = [json.loads(l) for l in Path("data/live_snapshot.ndjson").read_text(encoding="utf-8").splitlines() if l.strip()]
first = next(r for r in rows if r["status"] == "open" and r["workspace_id"].startswith("ws-prod"))
plan = {
    "workspace_id": first["workspace_id"],
    "ticket_id": first["ticket_id"],
    "action_commands": [f"sync_ticket {first['ticket_id']}", f"dispatch_workspace {first['workspace_id']}"],
    "source_event_id": first["event_id"],
}
Path("out/dispatch_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
Path("config/active_workspace.txt").write_text(first["workspace_id"] + "\n", encoding="utf-8")
sub = json.loads(Path("out/final_submission.json").read_text(encoding="utf-8"))
sub["selected_workspace_id"] = first["workspace_id"]
sub["selected_ticket"] = first["ticket_id"]
Path("out/final_submission.json").write_text(json.dumps(sub, indent=2) + "\n", encoding="utf-8")
PY
