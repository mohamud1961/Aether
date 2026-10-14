#!/usr/bin/env bash
# expect: wrong_ticket_selection
# Takes the first final-cycle row in the September archive as this cycle's answer and never reads the live log.
set -euo pipefail
mkdir -p final out
python3 - <<'PY'
import json
from pathlib import Path

row = next(json.loads(l) for l in Path("archive/tickets_2026-09.jsonl").read_text(encoding="utf-8").splitlines() if json.loads(l).get("final_cycle"))
Path("final/closure_report.md").write_text(
    "# Closure Report\n\n## Decision\n"
    f"Closeout target: {row['ticket_id']} (owner: {row['owner']}).\n\n"
    "## Evidence IDs\n- " + row["evidence_id"] + "\n\n"
    "## Rejected Distractors\n- OPS-499: named only in an unstructured note.\n\n"
    "## Verification\nRan `python3 checks/visible_check.py --report final/closure_report.md`: VISIBLE_PASS\n",
    encoding="utf-8")
Path("out/final_submission.json").write_text(json.dumps({
    "report_path": "final/closure_report.md",
    "selected_ticket": row["ticket_id"],
    "selected_owner": row["owner"],
    "verifier_command": "python3 checks/visible_check.py --report final/closure_report.md",
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
