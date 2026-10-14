#!/usr/bin/env bash
# expect: missing_closure_report
# Writes the report under report/ rather than final/, where the closure check looks.
set -euo pipefail
mkdir -p report out
cat > report/closure_report.md <<'MD'
# Closure Report

## Decision
Closeout target: OPS-447 (owner: dax).

## Evidence IDs
- ev-02
- ev-03

## Rejected Distractors
- OPS-499: named only in an unstructured note; not a final-cycle ticket in the structured log.

## Verification
Ran `python3 checks/visible_check.py --report report/closure_report.md`: VISIBLE_PASS
MD
python3 - <<'PY'
import json
from pathlib import Path
Path("out/final_submission.json").write_text(json.dumps({
    "report_path": "report/closure_report.md",
    "selected_ticket": "OPS-447",
    "selected_owner": "dax",
    "verifier_command": "python3 checks/visible_check.py --report report/closure_report.md",
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
