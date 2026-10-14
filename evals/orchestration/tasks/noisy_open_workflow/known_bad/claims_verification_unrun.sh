#!/usr/bin/env bash
# expect: missing_verifier_pass_event
# Writes the claimed VISIBLE_PASS, but the final edit renamed a required heading, so re-running the visible check on the report fails.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path

path = Path("final/closure_report.md")
text = path.read_text(encoding="utf-8")
old = "## Rejected Distractors"
if text.count(old) != 1:
    raise SystemExit("expected exactly one Rejected Distractors heading")
path.write_text(text.replace(old, "## Rejected Distractor"), encoding="utf-8")
PY
