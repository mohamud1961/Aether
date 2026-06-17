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

    if candidate.get("final_value") != truth["expected_final_value"]:
        reasons.append("final_value_mismatch")

    evidence_ids = candidate.get("evidence_ids", [])
    rejected_stale_ids = candidate.get("rejected_stale_ids", [])
    if not isinstance(evidence_ids, list):
        reasons.append("evidence_ids_not_list")
        evidence_ids = []
    if not isinstance(rejected_stale_ids, list):
        reasons.append("rejected_stale_ids_not_list")
        rejected_stale_ids = []

    for required in truth["required_evidence_ids"]:
        if required not in evidence_ids:
            reasons.append("missing_required_evidence_id")
            mismatches.append({"field": "evidence_id", "expected": required, "actual": "missing"})

    for required in truth["required_rejected_stale_ids"]:
        if required not in rejected_stale_ids:
            reasons.append("stale_id_not_rejected")
            mismatches.append({"field": "rejected_stale_id", "expected": required, "actual": "missing"})

    trace_dict = candidate.get("justification_trace")
    if not isinstance(trace_dict, dict):
        reasons.append("justification_trace_missing_or_invalid")
    else:
        for ev_id in evidence_ids:
            justif = trace_dict.get(ev_id, "")
            if not isinstance(justif, str) or len(justif) < 10:
                reasons.append("missing_evidence_justification")
        for ev_id in rejected_stale_ids:
            justif = trace_dict.get(ev_id, "")
            if not isinstance(justif, str) or len(justif) < 10:
                reasons.append("missing_rejection_justification")

    if not any(str(e.get("event_type")) in {"file_read", "tool_call"} for e in trace.get("events", [])):
        reasons.append("missing_evidence_access_trace")

    if not any(
        str(e.get("event_type")) == "verifier_run" and str(e.get("status", "")).lower() == "pass"
        for e in trace.get("events", [])
    ):
        reasons.append("missing_verifier_pass_event")

    reasons = sorted(set(reasons))
    return {
        "verdict": "pass" if not reasons else "fail",
        "score": 1.0 if not reasons else 0.0,
        "failure_class": "none" if not reasons else truth.get("primary_failure_class", "retrieval_reduction"),
        "reason_codes": reasons,
        "artifact_mismatches": mismatches,
    }
