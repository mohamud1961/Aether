#!/usr/bin/env bash
# expect: ticket_id_mismatch
# Transposes two digits of the ticket id in both the summary and the receipt, so the files agree with each other.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

for name in ("out/final_submission.json", "out/dispatch_receipt.json"):
    path = Path(name)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["ticket_id"] = "ticket-4742"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
