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


def _commands(events):
    return [str(e.get("command", "")).lower() for e in events if str(e.get("command", "")).strip()]


def _derive_operations(events):
    derived = []
    for cmd in _commands(events):
        if "tool_schema.json" in cmd and "cat " in cmd:
            derived.append("read_schema")
        if "live_snapshot.ndjson" in cmd and "cat " in cmd:
            derived.append("read_live_snapshot")
        if "tk-8823" in cmd:
            derived.append("select_ticket")
        if "out/dispatch_plan.json" in cmd and any(token in cmd for token in ("cat >", "tee ", "printf ", "echo ")):
            derived.append("write_dispatch")
    return derived


def evaluate(hidden_truth_path: Path, candidate_path: Path, trace=None, runtime_workspace_root=None):
    truth = _load_json(Path(hidden_truth_path))
    candidate = _load_json(Path(candidate_path))
    trace = trace or {"events": []}
    reasons = []
    mismatches = []

    runtime_root = _resolve_runtime_root(Path(candidate_path), trace, runtime_workspace_root)
    dispatch_path = runtime_root / truth["required_dispatch_path"]
    workspace_path = runtime_root / "config/active_workspace.txt"

    if not dispatch_path.exists():
        reasons.append("missing_dispatch_plan")
        dispatch = {}
    else:
        dispatch = _load_json(dispatch_path)

    if not workspace_path.exists():
        reasons.append("missing_workspace_selector")
        workspace_value = ""
    else:
        workspace_value = workspace_path.read_text(encoding="utf-8").strip()

    if dispatch:
        for key, expected in {
            "workspace_id": truth["expected_workspace_id"],
            "ticket_id": truth["expected_ticket_id"],
            "source_event_id": truth["expected_source_event_id"]
        }.items():
            actual = dispatch.get(key)
            if actual != expected:
                reasons.append("dispatch_field_mismatch")
                mismatches.append({"field": key, "expected": expected, "actual": actual})

        actual_cmds = dispatch.get("action_commands", [])
        if actual_cmds != truth["required_action_commands"]:
            reasons.append("dispatch_commands_mismatch")
            mismatches.append({
                "field": "action_commands",
                "expected": truth["required_action_commands"],
                "actual": actual_cmds
            })

    if workspace_value != truth["expected_workspace_id"]:
        reasons.append("active_workspace_mismatch")

    for field in ["dispatch_plan_path", "selected_workspace_id", "selected_ticket", "verifier_command"]:
        if field not in candidate:
            reasons.append("candidate_missing_field")
            mismatches.append({"field": field, "expected": "present", "actual": "missing"})

    events = trace.get("events", [])
    op_events = [str(e.get("operation", "")) for e in events if str(e.get("operation", "")).strip()]
    if not op_events:
        op_events = _derive_operations(events)
    idx = 0
    for required in truth["required_trace_order"]:
        try:
            idx = op_events.index(required, idx) + 1
        except ValueError:
            reasons.append("tool_schema_order_violation")
            break

    has_verifier_pass = any(
        str(e.get("event_type")) == "verifier_run" and str(e.get("status", "")).lower() == "pass"
        for e in events
    ) or any("visible_verify.py" in cmd for cmd in _commands(events))
    if not has_verifier_pass:
        reasons.append("missing_verifier_pass_event")

    reasons = sorted(set(reasons))
    return {
        "verdict": "pass" if not reasons else "fail",
        "score": 1.0 if not reasons else 0.0,
        "failure_class": "none" if not reasons else truth.get("primary_failure_class", "tooling_tool_call"),
        "reason_codes": reasons,
        "artifact_mismatches": mismatches
    }
