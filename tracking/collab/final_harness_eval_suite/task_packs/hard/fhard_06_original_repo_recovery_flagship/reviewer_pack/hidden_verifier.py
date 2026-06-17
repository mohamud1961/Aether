#!/usr/bin/env python3
import json
from pathlib import Path


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_env(path: Path):
    data = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


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
    fallback = (candidate_path.parent.parent).resolve()
    return fallback


def _commands_from_events(events):
    commands = []
    for event in events:
        cmd = str(event.get("command", "")).strip().lower()
        if cmd:
            commands.append(cmd)
    return commands


def _has_semantic_or_command(events, *, semantic_event: str, command_tokens):
    if any(str(e.get("event_type")) == semantic_event for e in events):
        return True
    commands = _commands_from_events(events)
    return any(all(token in cmd for token in command_tokens) for cmd in commands)


def evaluate(hidden_truth_path: Path, candidate_path: Path, trace=None, runtime_workspace_root=None):
    truth = _load_json(Path(hidden_truth_path))
    candidate = _load_json(Path(candidate_path))
    trace = trace or {"events": []}
    reasons = []
    mismatches = []

    runtime_root = _resolve_runtime_root(Path(candidate_path), trace, runtime_workspace_root)
    bundle_path = runtime_root / truth["required_bundle_path"]
    config_path = runtime_root / "services/catalog/config/runtime.env"

    if not bundle_path.exists():
        reasons.append("missing_recovery_bundle")
    if not config_path.exists():
        reasons.append("missing_runtime_config")

    bundle = {}
    env = {}
    if bundle_path.exists():
        bundle = _load_json(bundle_path)
        for key, expected in truth["expected_bundle"].items():
            actual = bundle.get(key)
            if actual != expected:
                reasons.append("bundle_field_mismatch")
                mismatches.append({"field": key, "expected": expected, "actual": actual})

    if config_path.exists():
        env = _parse_env(config_path)
        for key, expected in truth["expected_runtime"].items():
            actual = env.get(key)
            if actual != expected:
                reasons.append("runtime_env_mismatch")
                mismatches.append({"field": key, "expected": expected, "actual": actual})

    for required_field in ["output_path", "closure_ticket", "runtime_host", "queue_name", "verifier_command"]:
        if required_field not in candidate:
            reasons.append("candidate_missing_field")
            mismatches.append({"field": required_field, "expected": "present", "actual": "missing"})

    if candidate.get("output_path") != truth["required_bundle_path"]:
        reasons.append("candidate_output_path_mismatch")

    checks = truth["required_trace_checks"]
    events = trace.get("events", [])
    if len(events) < int(checks["min_event_count"]):
        reasons.append("insufficient_long_horizon_trace")
    if checks["requires_tool_call"] and not _has_semantic_or_command(
        events,
        semantic_event="tool_call",
        command_tokens=("python3",),
    ):
        reasons.append("missing_tool_call_event")
    if checks["requires_file_write"] and not _has_semantic_or_command(
        events,
        semantic_event="file_write",
        command_tokens=("cp ",),
    ):
        reasons.append("missing_file_write_event")
    has_verifier_pass = any(
        str(e.get("event_type")) == "verifier_run" and str(e.get("status", "")).lower() == "pass"
        for e in events
    ) or any("verify_recovery.py" in cmd for cmd in _commands_from_events(events))
    if checks["requires_verifier_pass"] and not has_verifier_pass:
        reasons.append("missing_verifier_pass_event")

    reasons = sorted(set(reasons))
    return {
        "verdict": "pass" if not reasons else "fail",
        "score": 1.0 if not reasons else 0.0,
        "failure_class": "none" if not reasons else truth.get("primary_failure_class", "verification_completion"),
        "reason_codes": reasons,
        "artifact_mismatches": mismatches
    }
