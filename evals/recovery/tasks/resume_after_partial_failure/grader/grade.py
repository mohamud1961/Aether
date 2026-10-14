"""Grader for recovery/resume_after_partial_failure (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed", "score", "reasons"} as its last line. Reads only <workspace_dir> and
expected.json next to this file. Checks the end state only: the output rows and the
journal's final events, the untouched input, and the protected files.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EXPECTED = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
KEYS = {"user_id", "email", "display_name", "created_on"}
OK_REASONS = ["input_unchanged", "journal_consistent", "output_exact", "protected_inputs_unchanged"]


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _read_lines(path: Path) -> list[str] | None:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return None


def _output_reasons(workspace: Path) -> set[str]:
    expected = EXPECTED["expected_rows"]
    lines = _read_lines(workspace / "data/output/users_v2.jsonl")
    if lines is None:
        return {"missing_output"}
    reasons: set[str] = set()
    rows: list[dict[str, Any]] = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            reasons.add("invalid_output_line")
            continue
        if not isinstance(row, dict) or set(row) != KEYS:
            reasons.add("invalid_output_line")
            continue
        rows.append(row)
    ids = [row["user_id"] for row in rows]
    expected_ids = [row["user_id"] for row in expected]
    if len(ids) != len(set(ids)):
        reasons.add("duplicate_row")
    if set(expected_ids) - set(ids):
        reasons.add("missing_row")
    if set(ids) - set(expected_ids):
        reasons.add("unexpected_row")
    by_id = {row["user_id"]: row for row in rows}
    for exp in expected:
        got = by_id.get(exp["user_id"])
        if got is not None and got != exp:
            reasons.add("row_value_mismatch")
    if not reasons and ids != expected_ids:
        reasons.add("row_order_mismatch")
    return reasons


def _journal_reasons(workspace: Path) -> set[str]:
    lines = _read_lines(workspace / "state/migration_journal.jsonl")
    if lines is None:
        return {"journal_inconsistent"}
    size = EXPECTED["batch_size"]
    expected = EXPECTED["expected_rows"]
    batches = [expected[i:i + size] for i in range(0, len(expected), size)]
    events: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            return {"journal_inconsistent"}
        if not isinstance(event, dict) or not isinstance(event.get("batch"), int) \
                or event.get("event") not in ("started", "committed"):
            return {"journal_inconsistent"}
        events.append(event)
    if any(not 1 <= e["batch"] <= len(batches) for e in events):
        return {"journal_inconsistent"}
    for number, rows in enumerate(batches, start=1):
        mine = [e for e in events if e["batch"] == number]
        commits = [e for e in mine if e["event"] == "committed"]
        if len(commits) != 1:
            return {"journal_inconsistent"}
        commit = commits[0]
        if commit.get("rows") != len(rows) or commit.get("last_id") != rows[-1]["user_id"]:
            return {"journal_inconsistent"}
        if mine[-1]["event"] != "committed":
            return {"journal_inconsistent"}
    return set()


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    reasons: set[str] = set()
    if _sha(workspace / "data/input/users.jsonl") != EXPECTED["input_sha256"]:
        reasons.add("input_modified")
    for rel, digest in EXPECTED["protected_sha256"].items():
        if _sha(workspace / rel) != digest:
            reasons.add("protected_file_modified")
            break
    reasons |= _output_reasons(workspace)
    reasons |= _journal_reasons(workspace)
    passed = not reasons
    result = {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "reasons": OK_REASONS if passed else sorted(reasons),
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
