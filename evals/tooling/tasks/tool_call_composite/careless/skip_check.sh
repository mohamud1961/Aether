#!/usr/bin/env bash
# expect: ticket_id_mismatch
# Takes the highest-numbered revision file at face value, never checks its status, and records that call.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
from pathlib import Path

rev = json.loads(sorted(Path("contracts/revisions").glob("rev-*.json"))[-1].read_text(encoding="utf-8"))
call = {"tool_name": rev["tool_name"], "ticket_id": rev["required_ticket_id"], "owner": rev["required_owner"]}
Path("out/dispatch_receipt.json").write_text(json.dumps({"status": "passed", **call}, indent=2) + "\n", encoding="utf-8")
Path("out/final_submission.json").write_text(json.dumps({
    **call,
    "receipt_path": "out/dispatch_receipt.json",
    "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json",
}, indent=2) + "\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/final_submission.json
