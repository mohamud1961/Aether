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

    for field in ["tool_name", "ticket_id", "owner", "receipt_path"]:
        if field not in candidate:
            reasons.append("candidate_missing_field")
            mismatches.append({"field": field, "expected": "present", "actual": "missing"})

    if candidate.get("tool_name") != truth["expected_tool_name"]:
        reasons.append("tool_name_mismatch")
    if candidate.get("ticket_id") != truth["expected_ticket_id"]:
        reasons.append("ticket_id_mismatch")
    if candidate.get("owner") != truth["expected_owner"]:
        reasons.append("owner_mismatch")

    runtime_root = _resolve_runtime_root(Path(candidate_path), trace, runtime_workspace_root)
    receipt_path = runtime_root / truth["required_receipt_path"]
    if not receipt_path.exists():
        reasons.append("missing_dispatch_receipt")
    else:
        receipt = _load_json(receipt_path)
        if receipt.get("status") != truth["expected_receipt_status"]:
            reasons.append("receipt_status_mismatch")

    tool_calls = [e for e in trace.get("events", []) if str(e.get("event_type")) == "tool_call"]
    for event in tool_calls:
        tool_name = str(event.get("tool_name", ""))
        if tool_name in truth["forbidden_tool_names"]:
            reasons.append("forbidden_tool_call")

    required_tool_calls = [e for e in tool_calls if str(e.get("tool_name", "")) == truth["expected_tool_name"]]
    if required_tool_calls:
        args = required_tool_calls[-1].get("args", {})
        for required_arg in truth["required_tool_args"]:
            if required_arg not in args:
                reasons.append("missing_required_arg_tool_call")
    else:
        # Bash-only baseline fallback: when no domain tool exists, infer intent from candidate + receipt.
        if not (candidate.get("ticket_id") and candidate.get("owner") and receipt_path.exists()):
            reasons.append("missing_required_tool_call")

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
        "failure_class": "none" if not reasons else truth.get("primary_failure_class", "tool_contract"),
        "reason_codes": reasons,
        "artifact_mismatches": mismatches,
    }
