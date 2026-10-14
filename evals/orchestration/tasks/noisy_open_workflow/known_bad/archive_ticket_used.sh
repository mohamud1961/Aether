#!/usr/bin/env bash
# expect: wrong_ticket_selection
# Takes the September archive's closeout (OPS-440, mira) as this cycle's target in the report and the submission.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

report = Path("final/closure_report.md")
text = report.read_text(encoding="utf-8")
text = text.replace("Closeout target: OPS-447 (owner: dax).", "Closeout target: OPS-440 (owner: mira).")
report.write_text(text, encoding="utf-8")
submission = Path("out/final_submission.json")
data = json.loads(submission.read_text(encoding="utf-8"))
data["selected_ticket"] = "OPS-440"
data["selected_owner"] = "mira"
submission.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
