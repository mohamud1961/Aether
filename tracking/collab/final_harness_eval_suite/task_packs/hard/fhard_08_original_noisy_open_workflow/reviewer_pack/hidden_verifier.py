#!/usr/bin/env python3
import json
from pathlib import Path


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_runtime_root(candidate_path: Path, trace: dict, runtime_workspace_root):
    if runtime_workspace_root:
        return Path(runtime_workspace_root)
    root = trace.get("meta", {}).get("workspace_root")
    if root:
        p = Path(str(root))
        if p.exists():
            return p
    for ancestor in candidate_path.resolve().parents:
        if ancestor.name == "workspace":
            return ancestor
    return (candidate_path.parent.parent).resolve()


def evaluate(hidden_truth_path: Path, candidate_path: Path, trace=None, runtime_workspace_root=None):
    truth = _load_json(Path(hidden_truth_path))
    candidate = _load_json(Path(candidate_path))
    trace = trace or {"events": []}
    reasons = []
    mismatches = []

    runtime_root = _resolve_runtime_root(Path(candidate_path), trace, runtime_workspace_root)
    report_path = runtime_root / truth["required_report_path"]
    if not report_path.exists():
        reasons.append("missing_closure_report")
        report = ""
    else:
        report = report_path.read_text(encoding="utf-8")

    required_sections = [
        "## Decision",
        "## Evidence IDs",
        "## Rejected Distractors",
        "## Verification"
    ]
    for section in required_sections:
        if section not in report:
            reasons.append("report_missing_section")
            mismatches.append({"field": section, "expected": "present", "actual": "missing"})

    if truth["expected_ticket_id"] not in report:
        reasons.append("wrong_ticket_selection")
    if truth["expected_owner"] not in report:
        reasons.append("wrong_owner_selection")

    for evidence_id in truth["required_evidence_ids"]:
        if evidence_id not in report:
            reasons.append("missing_required_evidence")
            mismatches.append({"field": "evidence_id", "expected": evidence_id, "actual": "missing"})

    for distractor in truth["required_rejected_distractors"]:
        if distractor not in report:
            reasons.append("distractor_not_rejected")
            mismatches.append({"field": "rejected_distractor", "expected": distractor, "actual": "missing"})

    for field in ["report_path", "selected_ticket", "selected_owner", "verifier_command"]:
        if field not in candidate:
            reasons.append("candidate_missing_field")
            mismatches.append({"field": field, "expected": "present", "actual": "missing"})

    if candidate.get("selected_ticket") != truth["expected_ticket_id"]:
        reasons.append("candidate_ticket_mismatch")
    if candidate.get("selected_owner") != truth["expected_owner"]:
        reasons.append("candidate_owner_mismatch")

    events = trace.get("events", [])
    has_verifier_pass = any(
        str(e.get("event_type")) == "verifier_run" and str(e.get("status", "")).lower() == "pass"
        for e in events
    ) or any("visible_check.py" in str(e.get("command", "")).lower() for e in events)
    if not has_verifier_pass:
        reasons.append("missing_verifier_pass_event")

    reasons = sorted(set(reasons))
    return {
        "verdict": "pass" if not reasons else "fail",
        "score": 1.0 if not reasons else 0.0,
        "failure_class": "none" if not reasons else truth.get("primary_failure_class", "retrieval_reduction"),
        "reason_codes": reasons,
        "artifact_mismatches": mismatches
    }
