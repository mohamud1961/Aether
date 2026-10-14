#!/usr/bin/env python3
"""Grader for tooling/tool_call_composite (v2).

python3 grade.py <workspace_dir> prints one JSON line {"passed", "score", "reasons"}.
Reads only <workspace_dir> and expected.json next to this file. The truth values are the
contract revision in force; out/ files are the solver's outputs, everything else is pristine.
"""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATE = "out/final_submission.json"
CANDIDATE_CHECKS = (
    ("tool_name", "tool_name_mismatch"),
    ("ticket_id", "ticket_id_mismatch"),
    ("owner", "owner_mismatch"),
    ("receipt_path", "receipt_path_mismatch"),
    ("verifier_command", "verifier_command_mismatch"),
)
RECEIPT_CHECKS = (
    ("status", "receipt_status", "receipt_status_mismatch"),
    ("tool_name", "tool_name", "receipt_tool_name_mismatch"),
    ("ticket_id", "ticket_id", "receipt_ticket_id_mismatch"),
    ("owner", "owner", "receipt_owner_mismatch"),
)


def _load(path: Path):
    """Return (value, problem) where problem is 'missing', 'invalid' or None."""
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "missing"
    except (OSError, ValueError):
        return None, "invalid"


def _pristine_reasons(workspace: Path, expected: dict) -> list[str]:
    reasons = []
    for rel, digest in sorted(expected["pristine_sha256"].items()):
        path = workspace / rel
        try:
            same = hashlib.sha256(path.read_bytes()).hexdigest() == digest
        except OSError:
            same = False
        if not same:
            reasons.append("other_file_modified")
    return reasons


def grade(workspace: Path, truth: dict, expected: dict) -> list[str]:
    reasons: list[str] = []
    candidate, problem = _load(workspace / CANDIDATE)
    if problem == "missing":
        return ["missing_candidate"]
    if problem == "invalid" or not isinstance(candidate, dict):
        reasons.append("candidate_json_invalid")
        candidate = {}
    if candidate.get("tool_name") in truth["forbidden_aliases"]:
        reasons.append("forbidden_alias_used")
    for key, code in CANDIDATE_CHECKS:
        if candidate.get(key) != truth[key]:
            reasons.append(code)

    receipt, problem = _load(workspace / truth["receipt_path"])
    if problem == "missing":
        reasons.append("receipt_missing")
    elif problem == "invalid" or not isinstance(receipt, dict):
        reasons.append("receipt_json_invalid")
    else:
        for key, truth_key, code in RECEIPT_CHECKS:
            if receipt.get(key) != truth[truth_key]:
                reasons.append(code)

    reasons += _pristine_reasons(workspace, expected)
    return reasons


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    expected = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
    reasons = sorted(set(grade(workspace, expected, expected)))
    passed = not reasons
    print(json.dumps({"passed": passed, "score": 1.0 if passed else 0.0,
                      "reasons": ["contract_call_recorded"] if passed else reasons}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
