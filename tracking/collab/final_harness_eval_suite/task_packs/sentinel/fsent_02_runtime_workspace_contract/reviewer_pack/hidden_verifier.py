#!/usr/bin/env python3
import json
from pathlib import Path


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(hidden_truth_path: Path, candidate_path: Path, trace=None, runtime_workspace_root=None):
    truth = _load_json(Path(hidden_truth_path))
    candidate = _load_json(Path(candidate_path))
    trace = trace or {"events": []}
    reasons = []
    mismatches = []

    if candidate.get("python_command") != truth["expected_python_command"]:
        reasons.append("python_command_mismatch")
    if candidate.get("workspace_root") != truth["expected_workspace_root"]:
        reasons.append("workspace_root_mismatch")
    if candidate.get("runner_command") != truth["expected_runner_command"]:
        reasons.append("runner_command_mismatch")

    runtime_classification = candidate.get("runtime_classification")
    if runtime_classification not in truth["expected_runtime_classification"]:
        reasons.append("runtime_classification_invalid")

    meta_root = str(trace.get("meta", {}).get("workspace_root", ""))
    if meta_root and meta_root != truth["expected_workspace_root"]:
        reasons.append("trace_workspace_root_mismatch")

    if not any(
        str(e.get("event_type")) == "verifier_run" and str(e.get("status", "")).lower() == "pass"
        for e in trace.get("events", [])
    ):
        reasons.append("missing_verifier_pass_event")

    for required_field in ["python_command", "workspace_root", "runner_command", "runtime_classification"]:
        if required_field not in candidate:
            mismatches.append({"field": required_field, "expected": "present", "actual": "missing"})

    reasons = sorted(set(reasons))
    return {
        "verdict": "pass" if not reasons else "fail",
        "score": 1.0 if not reasons else 0.0,
        "failure_class": "none" if not reasons else truth.get("primary_failure_class", "environment_toolchain"),
        "reason_codes": reasons,
        "artifact_mismatches": mismatches,
    }
