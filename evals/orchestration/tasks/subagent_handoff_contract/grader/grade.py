"""Grader for orchestration/subagent_handoff_contract (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed", "score", "reasons"} and exits 0. Reads <workspace_dir>/subagent_audit.json,
the sealed truth in expected.json next to this file, and the source files (hash-checked).
"""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_object(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def find_reasons(actual, expected):
    reasons = []
    if actual.get("agents_loaded") != expected["agents_loaded"] or actual.get("agent_order_is_deterministic") is not True:
        reasons.append("agent_loader_not_deterministic")
    if actual.get("frontmatter_summary") != expected["frontmatter_summary"]:
        reasons.append("agent_frontmatter_parse_mismatch")
    if actual.get("resolution_summary") != expected["resolution_summary"]:
        reasons.append("skill_or_mcp_refs_not_visible")
    if actual.get("task_packet") != expected["task_packet"]:
        reasons.append("task_packet_contract_missing")
    if actual.get("handoff") != expected["handoff"]:
        reasons.append("handoff_contract_missing")
    visibility = actual.get("visibility")
    if not isinstance(visibility, dict):
        visibility = {}
    if visibility.get("parent_visible_unresolved_risks") is not True or visibility != expected["visibility"]:
        reasons.append("unresolved_risks_hidden")
    if visibility.get("no_silent_background_execution") is not True:
        reasons.append("silent_background_execution_assumed")
    return reasons


def pristine_reasons(workspace, expected):
    reasons = []
    for rel, digest in sorted(expected["pristine_sha256"].items()):
        try:
            same = hashlib.sha256((workspace / rel).read_bytes()).hexdigest() == digest
        except OSError:
            same = False
        if not same:
            reasons.append("other_file_modified")
    return reasons


def emit(reasons):
    passed = not reasons
    result = {"passed": passed, "score": 1.0 if passed else 0.0,
              "reasons": ["subagent_audit_derived"] if passed else reasons}
    print(json.dumps(result, sort_keys=True))


def main():
    workspace = Path(sys.argv[1])
    expected = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
    actual = load_object(workspace / expected["audit_file"])
    if actual is None:
        emit(["audit_unreadable"])
        return 0
    emit(sorted(set(find_reasons(actual, expected) + pristine_reasons(workspace, expected))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
