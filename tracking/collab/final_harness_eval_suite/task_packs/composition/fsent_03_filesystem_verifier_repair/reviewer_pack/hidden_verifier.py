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
    target_path = runtime_root / truth["required_target_path"]
    decoy_path = runtime_root / truth["forbidden_decoy_path"]

    if not target_path.exists():
        reasons.append("missing_target_file")
    else:
        target_text = target_path.read_text(encoding="utf-8")
        if truth["required_text_snippet"] not in target_text:
            reasons.append("target_patch_missing")

    if decoy_path.exists():
        decoy_text = decoy_path.read_text(encoding="utf-8")
        if "retries: 5" in decoy_text:
            reasons.append("decoy_file_modified")

    if candidate.get("patched_target") != truth["required_target_path"]:
        reasons.append("candidate_target_mismatch")
    if not bool(candidate.get("decoy_untouched", False)):
        reasons.append("candidate_decoy_claim_missing")

    events = trace.get("events", [])
    has_verifier_pass = any(
        str(e.get("event_type")) == "verifier_run" and str(e.get("status", "")).lower() == "pass"
        for e in events
    ) or any("visible_check.py" in str(e.get("command", "")).lower() for e in events)
    if not has_verifier_pass:
        reasons.append("missing_verifier_pass_event")

    for field in ["patched_target", "verifier_command", "decoy_untouched"]:
        if field not in candidate:
            mismatches.append({"field": field, "expected": "present", "actual": "missing"})

    reasons = sorted(set(reasons))
    return {
        "verdict": "pass" if not reasons else "fail",
        "score": 1.0 if not reasons else 0.0,
        "failure_class": "none" if not reasons else truth.get("primary_failure_class", "filesystem_path"),
        "reason_codes": reasons,
        "artifact_mismatches": mismatches,
    }
