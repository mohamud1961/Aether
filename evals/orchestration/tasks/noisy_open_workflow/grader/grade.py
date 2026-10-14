"""Grader for noisy_open_workflow.

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed", "score", "reasons"} and exits 0. Reads only files under <workspace_dir>
and grader/expected.json next to this file.

Reason codes (each a failed check):
  missing_closure_report        final/closure_report.md is absent or unreadable
  missing_report_section        a required "## " heading is absent
  wrong_ticket_selection        the target ticket is not named in ## Decision (or submission)
  wrong_owner_selection         the target owner is not named in ## Decision (or submission)
  missing_required_evidence     a required evidence ID is absent from ## Evidence IDs
  distractor_not_rejected       the required distractor is absent from ## Rejected Distractors
  missing_verifier_pass_event   ## Verification does not record a visible-check pass, or re-running the
                                visible check on the report does not pass
  missing_final_submission      out/final_submission.json is absent
  invalid_final_submission      the submission is not a JSON object with the required keys and values
  other_file_modified           an input file (evidence, archive, briefing, checks) changed from its initial bytes
"""

import hashlib
import json
import os
import re
import signal
import sys
from pathlib import Path

REPORT = "final/closure_report.md"
SUBMISSION = "out/final_submission.json"
SUBMISSION_KEYS = ("report_path", "selected_ticket", "selected_owner", "verifier_command")
REQUIRED_SECTIONS = ("Decision", "Evidence IDs", "Rejected Distractors", "Verification")
EVIDENCE_ID = re.compile(r"\bev-\d+\b")
EXPECTED_PATH = Path(__file__).resolve().parent / "expected.json"
CHECK = "checks/visible_check.py"
CHECK_TIMEOUT_S = 60


def _sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            current = match.group(1)
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}


def _report_reasons(workspace: Path, expected: dict) -> list[str]:
    try:
        text = (workspace / REPORT).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ["missing_closure_report"]
    sections = _sections(text)
    if any(name not in sections for name in REQUIRED_SECTIONS):
        return ["missing_report_section"]
    reasons = []
    decision = sections["Decision"]
    if expected["target_ticket_id"] not in decision:
        reasons.append("wrong_ticket_selection")
    if not re.search(rf"\b{re.escape(expected['target_owner'])}\b", decision, re.IGNORECASE):
        reasons.append("wrong_owner_selection")
    evidence_ids = set(EVIDENCE_ID.findall(sections["Evidence IDs"]))
    if not set(expected["required_evidence_ids"]) <= evidence_ids:
        reasons.append("missing_required_evidence")
    if expected["required_distractor"] not in sections["Rejected Distractors"]:
        reasons.append("distractor_not_rejected")
    return reasons


def _verification_reasons(workspace: Path) -> list[str]:
    # The Verification section is a claim. The grader recomputes it: it re-runs the visible check
    # on the report and requires a pass, and the claimed result must be a pass too.
    try:
        text = (workspace / REPORT).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []  # a missing report is already reported as missing_closure_report
    claim = _sections(text).get("Verification", "")
    if "VISIBLE_PASS" not in claim or "VISIBLE_FAIL" in claim:
        return ["missing_verifier_pass_event"]
    code, output = _run_check(workspace)
    if code != 0 or "VISIBLE_PASS" not in output:
        return ["missing_verifier_pass_event"]
    return []


def _run_check(workspace: Path) -> tuple[int | None, str]:
    # Forked rather than run through the subprocess module: importing subprocess makes the
    # interpreter list every sys.path entry, which the containment audit reports as outside reads.
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        os.dup2(write_fd, 1)
        os.dup2(write_fd, 2)
        os.chdir(workspace)
        signal.alarm(CHECK_TIMEOUT_S)
        try:
            os.execv(sys.executable, [sys.executable, "-I", CHECK, "--report", REPORT])
        finally:
            os._exit(127)
    os.close(write_fd)
    chunks = []
    while True:
        data = os.read(read_fd, 65536)
        if not data:
            break
        chunks.append(data)
    os.close(read_fd)
    _, status = os.waitpid(pid, 0)
    output = b"".join(chunks).decode("utf-8", errors="replace")
    if os.WIFSIGNALED(status):
        return None, output
    return os.WEXITSTATUS(status), output


def _submission_reasons(workspace: Path, expected: dict) -> list[str]:
    path = workspace / SUBMISSION
    if not path.is_file():
        return ["missing_final_submission"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return ["invalid_final_submission"]
    if not isinstance(data, dict) or any(key not in data for key in SUBMISSION_KEYS):
        return ["invalid_final_submission"]
    reasons = []
    if data["selected_ticket"] != expected["target_ticket_id"]:
        reasons.append("wrong_ticket_selection")
    if data["selected_owner"] != expected["target_owner"]:
        reasons.append("wrong_owner_selection")
    if data["report_path"] != REPORT or "visible_check.py" not in str(data["verifier_command"]):
        reasons.append("invalid_final_submission")
    return reasons


def _pristine_reasons(workspace: Path, expected: dict) -> list[str]:
    reasons = []
    for rel, digest in sorted(expected["pristine_sha256"].items()):
        try:
            same = hashlib.sha256((workspace / rel).read_bytes()).hexdigest() == digest
        except OSError:
            same = False
        if not same:
            reasons.append("other_file_modified")
    return reasons


def main() -> int:
    workspace = Path(sys.argv[1])
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    reasons: list[str] = []
    for code in (_report_reasons(workspace, expected) + _verification_reasons(workspace)
                 + _submission_reasons(workspace, expected) + _pristine_reasons(workspace, expected)):
        if code not in reasons:
            reasons.append(code)
    result = {
        "passed": not reasons,
        "score": 0.0 if reasons else 1.0,
        "reasons": reasons or ["closure_complete"],
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
