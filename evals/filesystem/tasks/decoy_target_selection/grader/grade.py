"""Grader for filesystem/decoy_target_selection (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed", "score", "reasons"} as its last line. Reads only <workspace_dir> and
expected.json next to this file.

The target file, the required effective timeout and the pristine hashes of every
initial file are sealed in expected.json. The effective timeout is resolved the way
docs/config_layers.md describes: the environment overlay's timeout wins, otherwise
base.yaml's timeout applies. Editing base.yaml or the manifest therefore cannot move
the target.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SUBMISSION = "out/final_submission.json"
OK_REASONS = (
    "submission_contract_ok",
    "effective_timeout_ok",
    "target_only_change",
    "decoy_untouched",
    "other_files_unchanged",
)


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None


def _timeout_value(text: str) -> int | None:
    for line in text.splitlines():
        head, sep, value = line.partition(":")
        if sep and head.strip() == "timeout" and value.strip().isdigit():
            return int(value.strip())
    return None


def _mask_timeout(line: str) -> str:
    head, sep, value = line.partition(":")
    if sep and head.strip() == "timeout" and value.strip().isdigit():
        return "timeout: <n>"
    return line


def _submission_reasons(workspace: Path, expected: dict[str, Any]) -> list[str]:
    text = _read_text(workspace / SUBMISSION)
    if text is None:
        return ["missing_final_submission"]
    try:
        submission = json.loads(text)
    except ValueError:
        return ["candidate_unparseable"]
    if not isinstance(submission, dict):
        return ["candidate_unparseable"]
    reasons: list[str] = []
    if submission.get("patched_target") != expected["target_path"]:
        reasons.append("candidate_target_mismatch")
    effective = submission.get("effective_timeout_s")
    if type(effective) is not int or effective != expected["required_effective_timeout_s"]:
        reasons.append("candidate_effective_timeout_mismatch")
    if submission.get("verifier_command") != expected["required_verifier_command"]:
        reasons.append("missing_verifier_pass_event")
    if submission.get("decoy_untouched") is not True:
        reasons.append("candidate_decoy_claim_missing")
    return reasons


def _target_reasons(workspace: Path, expected: dict[str, Any]) -> list[str]:
    text = _read_text(workspace / expected["target_path"])
    if text is None:
        return ["missing_target_file"]
    reasons: list[str] = []
    masked = [_mask_timeout(line) for line in text.splitlines()]
    pristine = [_mask_timeout(line) for line in expected["target_pristine_text"].splitlines()]
    if masked != pristine:
        reasons.append("target_collateral_edit")
    base = _read_text(workspace / expected["base_path"])
    if base is None:
        reasons.append("missing_base_file")
    else:
        effective = _timeout_value(text)
        if effective is None:
            effective = _timeout_value(base)
        if effective != expected["required_effective_timeout_s"]:
            reasons.append("effective_timeout_mismatch")
    return reasons


def _pristine_reasons(workspace: Path, expected: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    decoys = set(expected["decoy_paths"])
    for rel, digest in sorted(expected["pristine_sha256"].items()):
        if rel == expected["target_path"]:
            continue
        if _sha256(workspace / rel) == digest:
            continue
        reasons.append("decoy_file_modified" if rel in decoys else "other_file_modified")
    return reasons


def grade(workspace: Path, expected: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = (
        _submission_reasons(workspace, expected)
        + _target_reasons(workspace, expected)
        + _pristine_reasons(workspace, expected)
    )
    unique = sorted(set(reasons))
    return (not unique, unique)


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    expected = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
    passed, reasons = grade(workspace, expected)
    result = {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "reasons": list(OK_REASONS) if passed else reasons,
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
