#!/usr/bin/env bash
# expect: selected_workspace_mismatch
# Writes plan, selector and submission with the right shape and plausible values, copied from the first line of the snapshot, without deriving anything.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
from pathlib import Path

plan = {
    "workspace_id": "ws-prod-7",
    "ticket_id": "TK-8823",
    "action_commands": ["sync_ticket TK-8823", "dispatch_workspace ws-prod-7"],
    "source_event_id": "evt-102",
}
Path("out/dispatch_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
Path("config/active_workspace.txt").write_text("ws-prod-7\n", encoding="utf-8")
Path("out/final_submission.json").write_text(json.dumps({
    "dispatch_plan_path": "out/dispatch_plan.json",
    "selected_workspace_id": "ws-prod-7",
    "selected_ticket": "TK-8823",
    "verifier_command": "python3 scripts/visible_verify.py --dispatch out/dispatch_plan.json --workspace config/active_workspace.txt",
}, indent=2) + "\n", encoding="utf-8")
PY
