#!/usr/bin/env python3
"""Grader for tooling/tool_schema_workspace_mix (v2).

python3 grade.py <workspace_dir> prints one JSON line {"passed", "score", "reasons"}.
Reads only <workspace_dir> and expected.json next to this file. Values are the truth for the
latest-event-per-ticket selection; every input file is pristine (sealed by hash), except the
selector, which the task asks the solver to update.
"""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "missing"
    except (OSError, ValueError):
        return None, "invalid"


def _plan_reasons(workspace: Path, truth: dict) -> list[str]:
    plan, problem = _json(workspace / truth["dispatch_plan_path"])
    if problem is not None or not isinstance(plan, dict):
        return ["missing_dispatch_plan"]
    reasons = []
    if sorted(plan) != truth["dispatch_fields"]:
        reasons.append("dispatch_fields_mismatch")
    if plan.get("workspace_id") != truth["workspace_id"]:
        reasons.append("selected_workspace_mismatch")
    if plan.get("ticket_id") != truth["ticket_id"]:
        reasons.append("selected_ticket_mismatch")
    if plan.get("source_event_id") != truth["source_event_id"]:
        reasons.append("source_event_mismatch")
    if plan.get("action_commands") != truth["action_commands"]:
        reasons.append("action_commands_mismatch")
    return reasons


def _selector_reasons(workspace: Path, truth: dict) -> list[str]:
    try:
        value = (workspace / truth["selector_path"]).read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return ["selector_mismatch"]
    return [] if value == truth["workspace_id"] else ["selector_mismatch"]


def _submission_reasons(workspace: Path, truth: dict) -> list[str]:
    sub, problem = _json(workspace / "out/final_submission.json")
    if problem is not None or not isinstance(sub, dict):
        return ["missing_final_submission"]
    reasons = []
    if sub.get("dispatch_plan_path") != truth["dispatch_plan_path"]:
        reasons.append("dispatch_plan_path_mismatch")
    if sub.get("selected_workspace_id") != truth["workspace_id"]:
        reasons.append("submission_workspace_mismatch")
    if sub.get("selected_ticket") != truth["ticket_id"]:
        reasons.append("submission_ticket_mismatch")
    if sub.get("verifier_command") != truth["verifier_command"]:
        reasons.append("verifier_command_mismatch")
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
    workspace = Path(sys.argv[1]).resolve()
    expected = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
    reasons = sorted(set(
        _plan_reasons(workspace, expected)
        + _selector_reasons(workspace, expected)
        + _submission_reasons(workspace, expected)
        + _pristine_reasons(workspace, expected)
    ))
    passed = not reasons
    print(json.dumps({"passed": passed, "score": 1.0 if passed else 0.0,
                      "reasons": ["dispatch_selection_ok"] if passed else reasons}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
