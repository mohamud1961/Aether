#!/usr/bin/env bash
# expect: receipt_status_mismatch
# Correct call and summary, but the receipt records a failed dispatch.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

path = Path("out/dispatch_receipt.json")
receipt = json.loads(path.read_text(encoding="utf-8"))
receipt["status"] = "failed"
path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
PY
