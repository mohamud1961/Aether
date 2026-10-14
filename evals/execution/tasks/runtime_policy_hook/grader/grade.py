"""Grader for runtime_policy_hook (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed", "score", "reasons"} and exits 0. Reads <workspace_dir> and expected.json next to this file.

The expected event order and flags for session s-7731, tool call tc-0917 are sealed in expected.json.
They were derived from the pristine evidence (logs/hook_events.jsonl ordered by seq, and
logs/tool_calls.jsonl). Every evidence file is hashed, so an edited log cannot move the target.
policy_audit.json is the only file the solver writes and is not hashed.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

GRADER_DIR = Path(__file__).resolve().parent
AUDIT = "policy_audit.json"


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _load_audit(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, "missing_policy_audit"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "malformed_policy_audit"
    if not isinstance(payload, dict):
        return None, "malformed_policy_audit"
    return payload, None


def _check_audit(ws: Path, expected: dict[str, Any], reasons: list[str]) -> None:
    audit, problem = _load_audit(ws / AUDIT)
    if audit is None:
        reasons.append(problem or "missing_policy_audit")
        return
    if audit.get("events") != expected["expected_events"]:
        reasons.append("hook_order_mismatch")
    flags = expected["expected_flags"]
    if audit.get("denied_observation_visible") is not flags["denied_observation_visible"]:
        reasons.append("denial_not_visible")
    if audit.get("denied_action_mutated_workspace") is not flags["denied_action_mutated_workspace"]:
        reasons.append("denial_mutated_workspace")
    if audit.get("arguments_mutated") is not flags["arguments_mutated"]:
        reasons.append("arguments_mutated")


def _check_evidence(ws: Path, expected: dict[str, Any], reasons: list[str]) -> None:
    for rel, digest in sorted(expected["pristine_sha256"].items()):
        if _sha(ws / rel) != digest:
            reasons.append("evidence_file_modified")
            return


def main() -> int:
    ws = Path(sys.argv[1]).resolve()
    expected = json.loads((GRADER_DIR / "expected.json").read_text(encoding="utf-8"))
    reasons: list[str] = []
    _check_audit(ws, expected, reasons)
    _check_evidence(ws, expected, reasons)
    reasons = sorted(set(reasons))
    passed = not reasons
    result = {"passed": passed, "score": 1.0 if passed else 0.0,
              "reasons": ["policy_audit_ok"] if passed else reasons}
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
