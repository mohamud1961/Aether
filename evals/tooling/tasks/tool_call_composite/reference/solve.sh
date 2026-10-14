#!/usr/bin/env bash
# Resolves the active contract revision through the pointer file, records the dispatch receipt,
# writes the candidate summary and runs the visible check on it.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path

root = Path(".")
pointer = json.loads((root / "contracts/tool_schema.json").read_text(encoding="utf-8"))
revision = json.loads(
    (root / "contracts/revisions" / f"{pointer['active_revision']}.json").read_text(encoding="utf-8")
)
if revision["status"] != "active":
    raise SystemExit(f"revision {revision['revision']} is not active")

tool_name = revision["tool_name"]
ticket_id = revision["required_ticket_id"]
owner = revision["required_owner"]
receipt_path = "out/dispatch_receipt.json"
verifier_command = "python3 checks/visible_check.py --candidate out/final_submission.json"

Path("out").mkdir(exist_ok=True)
Path(receipt_path).write_text(
    json.dumps(
        {
            "status": revision["required_receipt_status"],
            "tool_name": tool_name,
            "ticket_id": ticket_id,
            "owner": owner,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
Path("out/final_submission.json").write_text(
    json.dumps(
        {
            "tool_name": tool_name,
            "ticket_id": ticket_id,
            "owner": owner,
            "receipt_path": receipt_path,
            "verifier_command": verifier_command,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY
python3 checks/visible_check.py --candidate out/final_submission.json
