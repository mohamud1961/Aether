#!/usr/bin/env bash
# expect: dispatch_plan_path_mismatch
# Writes the right plan, but to config/ rather than out/, and points the submission at the wrong file.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
from pathlib import Path

plan = {
    "workspace_id": "ws-prod-2",
    "ticket_id": "TK-8821",
    "action_commands": ["sync_ticket TK-8821", "dispatch_workspace ws-prod-2"],
    "source_event_id": "evt-105",
}
Path("config/dispatch_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
Path("config/active_workspace.txt").write_text("ws-prod-2\n", encoding="utf-8")
Path("out/final_submission.json").write_text(json.dumps({
    "dispatch_plan_path": "config/dispatch_plan.json",
    "selected_workspace_id": "ws-prod-2",
    "selected_ticket": "TK-8821",
    "verifier_command": "python3 scripts/visible_verify.py --dispatch config/dispatch_plan.json --workspace config/active_workspace.txt",
}, indent=2) + "\n", encoding="utf-8")
PY
