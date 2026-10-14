#!/usr/bin/env bash
# expect: wrong_ticket_selection
# Decision follows the handwritten note (OPS-499) instead of the structured ticket log.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

def replace_once(path, old, new):
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one occurrence of {old!r} in {path}")
    target.write_text(text.replace(old, new), encoding="utf-8")

replace_once("final/closure_report.md", "Closeout target: OPS-447 (owner: dax).", "Closeout target: OPS-499 (owner: unassigned).")
submission = Path("out/final_submission.json")
data = json.loads(submission.read_text(encoding="utf-8"))
data["selected_ticket"] = "OPS-499"
data["selected_owner"] = "unassigned"
submission.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
