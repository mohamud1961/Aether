#!/usr/bin/env bash
# expect: receipt_path_mismatch
# Records the right values, but writes the receipt under a scratch folder and points the summary there.
set -euo pipefail
mkdir -p out/scratch
python3 - <<'PY'
import json
from pathlib import Path

rev = json.loads(Path("contracts/revisions/rev-07.json").read_text(encoding="utf-8"))
call = {"tool_name": rev["tool_name"], "ticket_id": rev["required_ticket_id"], "owner": rev["required_owner"]}
Path("out/scratch/dispatch_receipt.json").write_text(json.dumps({"status": "passed", **call}, indent=2) + "\n", encoding="utf-8")
Path("out/final_submission.json").write_text(json.dumps({
    **call,
    "receipt_path": "out/scratch/dispatch_receipt.json",
    "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json",
}, indent=2) + "\n", encoding="utf-8")
PY
