#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _coerce_handoff_steps(value) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        steps = value.get("steps")
        if isinstance(steps, list):
            return len(steps)
        return 1 if value else 0
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0
        try:
            return max(0, int(stripped))
        except ValueError:
            return 1
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def evaluate(hidden_truth_path: Path, candidate_path: Path, trace=None, runtime_workspace_root=None):
    truth = _load_json(Path(hidden_truth_path))
    candidate = _load_json(Path(candidate_path))
    trace = trace or {"events": []}
    reasons = []
    mismatches = []

    runtime_root = _resolve_runtime_root(Path(candidate_path), trace, runtime_workspace_root)
    bundle_path = runtime_root / truth["required_bundle_path"]
    if not bundle_path.exists():
        reasons.append("missing_final_bundle")
    else:
        bundle = _load_json(bundle_path)
        if bundle.get("artifact_id") != truth["expected_artifact_id"]:
            reasons.append("artifact_id_mismatch")

    if candidate.get("bundle_path") != truth["required_bundle_path"]:
        reasons.append("candidate_bundle_path_mismatch")

    handoff_steps = _coerce_handoff_steps(candidate.get("handoff_steps", 0))
    if handoff_steps < int(truth["minimum_handoff_steps"]):
        reasons.append("insufficient_handoff_steps")

    if bundle_path.exists():
        observed_sha = _sha256(bundle_path)
        if candidate.get("bundle_sha256") != observed_sha:
            reasons.append("bundle_sha_mismatch")
            mismatches.append({"field": "bundle_sha256", "expected": observed_sha, "actual": candidate.get("bundle_sha256")})

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
        "failure_class": "none" if not reasons else truth.get("primary_failure_class", "long_horizon_orchestration"),
        "reason_codes": reasons,
        "artifact_mismatches": mismatches,
    }
