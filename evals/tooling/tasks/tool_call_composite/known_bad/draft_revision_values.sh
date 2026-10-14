#!/usr/bin/env bash
# expect: ticket_id_mismatch
# Uses the draft rev-08 values (ticket-4482, owner-tomas) consistently in the receipt and the summary.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

for name in ("out/final_submission.json", "out/dispatch_receipt.json"):
    path = Path(name)
    data = json.loads(path.read_text(encoding="utf-8"))
    if "ticket_id" in data:
        data["ticket_id"] = "ticket-4482"
    if "owner" in data:
        data["owner"] = "owner-tomas"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
