#!/usr/bin/env bash
# expect: wrong_ticket_selection
# Writes a report and submission with every section present and a plausible decision taken from the calendar draft, without reading the ticket log.
set -euo pipefail
mkdir -p final out
cat > final/closure_report.md <<'MD'
# Closure Report

## Decision
Closeout target: OPS-440 (owner: mira).

## Evidence IDs
- ar-01

## Rejected Distractors
- OPS-499: rehearsal board note.

## Verification
Ran `python3 checks/visible_check.py --report final/closure_report.md`: VISIBLE_PASS
MD
python3 - <<'PY'
import json
from pathlib import Path
Path("out/final_submission.json").write_text(json.dumps({
    "report_path": "final/closure_report.md",
    "selected_ticket": "OPS-440",
    "selected_owner": "mira",
    "verifier_command": "python3 checks/visible_check.py --report final/closure_report.md",
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
