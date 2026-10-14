#!/usr/bin/env bash
# expect: selected_ticket_mismatch
# Takes the first open production row in file order, writes the outputs, and never checks that the ticket is still open.
set -euo pipefail
mkdir -p out
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
Path("out/final_submission.json").write_text(json.dumps({
    "dispatch_plan_path": "out/dispatch_plan.json",
    "selected_workspace_id": first["workspace_id"],
    "selected_ticket": first["ticket_id"],
    "verifier_command": "python3 scripts/visible_verify.py --dispatch out/dispatch_plan.json --workspace config/active_workspace.txt",
}, indent=2) + "\n", encoding="utf-8")
PY
