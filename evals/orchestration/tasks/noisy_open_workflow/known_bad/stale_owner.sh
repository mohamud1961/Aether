#!/usr/bin/env bash
# expect: wrong_owner_selection
# Right ticket, but the owner is taken from the earlier closed ticket's row instead of the final-cycle row.
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

replace_once("final/closure_report.md", "Closeout target: OPS-447 (owner: dax).", "Closeout target: OPS-447 (owner: mira).")
submission = Path("out/final_submission.json")
data = json.loads(submission.read_text(encoding="utf-8"))
data["selected_owner"] = "mira"
submission.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
