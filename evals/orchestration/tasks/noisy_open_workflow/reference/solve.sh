#!/usr/bin/env bash
# Produces the correct final state from the initial workspace: closure report and submission.
# The decision comes from the structured ticket log: the final-cycle ticket, its owner, and the evidence
# IDs of the final-cycle rows. The distractor is the ticket ID named in the handwritten note, which is not
# in the structured log. The verification section records the real result of the visible check.
set -euo pipefail
python3 - <<'PY'
import json
import re
import subprocess
import sys
from pathlib import Path

LOG = Path("evidence/tickets.jsonl")
NOTES = Path("evidence/handwritten_scan_notes.txt")
REPORT = Path("final/closure_report.md")
SUBMISSION = Path("out/final_submission.json")
REPORT_PATH = "final/closure_report.md"
VERIFIER_COMMAND = "python3 checks/visible_check.py --report final/closure_report.md"
CHECK = [sys.executable, "checks/visible_check.py", "--report", REPORT_PATH]

rows = [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
final_rows = [row for row in rows if row.get("final_cycle")]
if not final_rows:
    raise SystemExit("no final-cycle rows in the structured log")
tickets = {row["ticket_id"] for row in final_rows}
if len(tickets) != 1:
    raise SystemExit(f"final-cycle rows name more than one ticket: {sorted(tickets)}")
ticket = final_rows[0]["ticket_id"]
owner = final_rows[0]["owner"]
owners = {row["owner"] for row in final_rows}
if len(owners) != 1:
    raise SystemExit(f"final-cycle rows name more than one owner: {sorted(owners)}")
evidence_ids = [row["evidence_id"] for row in final_rows]

note = re.search(r"OPS-\d+", NOTES.read_text(encoding="utf-8"))
if note is None or note.group(0) == ticket:
    raise SystemExit("handwritten note does not name a distractor ticket")
distractor = note.group(0)


def render(verification_body: str) -> str:
    lines = [
        "# Closure Report",
        "",
        "## Decision",
        f"Closeout target: {ticket} (owner: {owner}).",
        "",
        "## Evidence IDs",
        *[f"- {evidence_id}" for evidence_id in evidence_ids],
        "",
        "## Rejected Distractors",
        f"- {distractor}: named only in an unstructured note; not a final-cycle ticket in the structured log.",
        "",
        "## Verification",
        verification_body,
        "",
    ]
    return "\n".join(lines)


REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(render("Visible check not yet run."), encoding="utf-8")
first = subprocess.run(CHECK, capture_output=True, text=True, check=False)
if first.returncode != 0:
    raise SystemExit(f"visible check failed: {first.stdout}{first.stderr}")
REPORT.write_text(render(f"Ran `{VERIFIER_COMMAND}`:\n\n{first.stdout.strip()}"), encoding="utf-8")
second = subprocess.run(CHECK, capture_output=True, text=True, check=False)
if second.returncode != 0:
    raise SystemExit(f"visible check failed on final report: {second.stdout}{second.stderr}")

SUBMISSION.parent.mkdir(parents=True, exist_ok=True)
SUBMISSION.write_text(
    json.dumps(
        {
            "report_path": REPORT_PATH,
            "selected_ticket": ticket,
            "selected_owner": owner,
            "verifier_command": VERIFIER_COMMAND,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY
