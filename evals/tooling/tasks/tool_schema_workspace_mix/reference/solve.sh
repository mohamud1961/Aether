#!/usr/bin/env bash
# Run from the project root. Reads the contract and the environment config, reduces the append-only
# snapshot to the latest event per ticket, selects the open production ticket with the smallest
# priority, then writes the dispatch plan, the selector and the submission, and runs the verifier.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path

root = Path(".")
contract = json.loads((root / "ops/contracts/tool_schema.json").read_text(encoding="utf-8"))
scope = contract["selection"]["candidate_scope"]
env = json.loads((root / scope["file"]).read_text(encoding="utf-8"))
node = env
for key in scope["path"]:
    node = node[key]
prefix = node

rows = [json.loads(line) for line in (root / contract["snapshot"]).read_text(encoding="utf-8").splitlines() if line.strip()]
latest = {}
for row in rows:
    key = row["ticket_id"]
    if key not in latest or row["seq"] > latest[key]["seq"]:
        latest[key] = row

candidates = [
    row for row in latest.values()
    if row["status"] == contract["selection"]["candidate_status"]
    and str(row["workspace_id"]).startswith(prefix)
]
if not candidates:
    raise SystemExit("no open production ticket in the latest snapshot state")
chosen = min(candidates, key=lambda r: (r["priority"], r["workspace_id"], r["ticket_id"]))

plan = {
    "workspace_id": chosen["workspace_id"],
    "ticket_id": chosen["ticket_id"],
    "action_commands": [t.format(**chosen) for t in contract["action_templates"]],
    "source_event_id": chosen["event_id"],
}
if sorted(plan) != sorted(contract["dispatch_required_fields"]):
    raise SystemExit("plan fields do not match the contract")

(root / "out").mkdir(exist_ok=True)
(root / "out/dispatch_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
(root / "config/active_workspace.txt").write_text(chosen["workspace_id"] + "\n", encoding="utf-8")
submission = {
    "dispatch_plan_path": "out/dispatch_plan.json",
    "selected_workspace_id": chosen["workspace_id"],
    "selected_ticket": chosen["ticket_id"],
    "verifier_command": "python3 scripts/visible_verify.py --dispatch out/dispatch_plan.json --workspace config/active_workspace.txt",
}
(root / "out/final_submission.json").write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
PY
python3 scripts/visible_verify.py --dispatch out/dispatch_plan.json --workspace config/active_workspace.txt
