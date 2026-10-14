"""Grader for context/state_reconstruction_long_log (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed", "score", "reasons"} as its last line. Reads <workspace_dir> and
expected_truth.json next to this file.

The effective value of every key, the sorted changed-since-C3 keys and the pristine hash of every
input file are sealed in expected_truth.json, so a wrong replay cannot be accepted and an edited
log cannot move the target.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
OK_REASONS = ("final_state_ok", "changed_since_c3_ok", "inputs_unchanged")
FINAL = "out/final_state.json"
CHANGED = "out/changed_since_c3.json"


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _load(path: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "missing"
    except (OSError, ValueError):
        return None, "invalid"


def _input_reasons(workspace: Path, truth: dict[str, Any]) -> list[str]:
    for rel, digest in sorted(truth["input_sha256"].items()):
        if _sha256(workspace / rel) != digest:
            return ["input_file_modified"]
    return []


def _final_reasons(workspace: Path, truth: dict[str, Any]) -> list[str]:
    value, problem = _load(workspace / FINAL)
    if problem == "missing":
        return ["missing_final_state"]
    expected = truth["final_state"]
    if problem or not isinstance(value, dict):
        return ["invalid_final_state"]
    reasons: list[str] = []
    if set(value) != set(expected):
        reasons.append("final_state_key_mismatch")
    if any(key in expected and (type(value[key]) is not str or value[key] != expected[key]) for key in value):
        reasons.append("final_state_value_mismatch")
    return reasons


def _changed_reasons(workspace: Path, truth: dict[str, Any]) -> list[str]:
    value, problem = _load(workspace / CHANGED)
    if problem == "missing":
        return ["missing_changed_since_c3"]
    if problem or not isinstance(value, dict) or not isinstance(value.get("changed_keys"), list):
        return ["invalid_changed_since_c3"]
    if value["changed_keys"] != truth["changed_since_c3"]:
        return ["changed_since_c3_mismatch"]
    return []


def grade(workspace: Path, truth: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = _input_reasons(workspace, truth)
    if not reasons:
        reasons = _final_reasons(workspace, truth) + _changed_reasons(workspace, truth)
    unique = sorted(set(reasons))
    return (not unique, unique)


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    truth = json.loads((HERE / "expected_truth.json").read_text(encoding="utf-8"))
    passed, reasons = grade(workspace, truth)
    result = {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "reasons": list(OK_REASONS) if passed else reasons,
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
