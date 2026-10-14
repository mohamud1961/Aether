#!/usr/bin/env bash
# expect: missing_final_submission
# Writes the correct plan and selector, then stops before writing the submission.
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
Path("out/dispatch_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
Path("config/active_workspace.txt").write_text("ws-prod-2\n", encoding="utf-8")
PY
