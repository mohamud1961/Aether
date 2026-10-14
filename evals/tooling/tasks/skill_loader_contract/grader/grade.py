#!/usr/bin/env python3
"""Grader for tooling/skill_loader_contract (v2).

python3 grade.py <workspace_dir> prints one JSON line {"passed", "score", "reasons"}.
Reads only <workspace_dir> and expected.json next to this file. skill_audit.json must equal the
audit the loader derives from skills/ and loader/. Every source file must be unchanged.
"""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _section_reasons(audit: dict, truth: dict) -> list[str]:
    reasons = []
    order = audit.get("skill_order_is_deterministic")
    if audit.get("skills_discovered") != truth["skills_discovered"]:
        if sorted(audit.get("skills_discovered") or []) != sorted(truth["skills_discovered"]):
            reasons.append("skill_discovery_set_mismatch")
        else:
            reasons.append("skill_discovery_not_deterministic")
    if order is not True or truth["skill_order_is_deterministic"] is not True:
        reasons.append("skill_discovery_not_deterministic")
    if audit.get("frontmatter_summary") != truth["frontmatter_summary"]:
        reasons.append("skill_frontmatter_parse_mismatch")
    if audit.get("collision_reason_codes") != truth["collision_reason_codes"]:
        reasons.append("skill_collision_handling_missing")
    if audit.get("selection_reason_codes") != truth["selection_reason_codes"]:
        reasons.append("skill_missing_reason_codes_absent")
    if audit.get("visible_context") != truth["visible_context"]:
        reasons.append("skill_context_not_visible_or_bounded")
    if audit.get("metadata_retention") != truth["metadata_retention"]:
        reasons.append("skill_metadata_not_retained_safely")
    if audit.get("hidden_behavior") != truth["hidden_behavior"]:
        reasons.append("hidden_prompt_mutation_detected")
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
    reasons: list[str] = []
    try:
        audit = json.loads((workspace / expected["audit_file"]).read_text(encoding="utf-8"))
    except FileNotFoundError:
        reasons.append("missing_skill_audit")
        audit = None
    except (OSError, ValueError):
        reasons.append("skill_audit_unreadable")
        audit = None
    if isinstance(audit, dict):
        if set(audit) != set(expected["audit"]):
            reasons.append("skill_audit_keys_changed")
        reasons += _section_reasons(audit, expected["audit"])
    elif audit is not None:
        reasons.append("skill_audit_unreadable")
    reasons += _pristine_reasons(workspace, expected)
    reasons = sorted(set(reasons))
    passed = not reasons
    print(json.dumps({"passed": passed, "score": 1.0 if passed else 0.0,
                      "reasons": ["skill_loader_audit_ok"] if passed else reasons}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
