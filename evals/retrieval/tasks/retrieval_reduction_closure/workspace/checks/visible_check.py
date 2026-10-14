#!/usr/bin/env python3
"""Readiness gate: checks the candidate's keys and types only (NOT the values)."""
import argparse
import json
from pathlib import Path

VERIFIER = "python3 checks/visible_check.py --candidate out/final_submission.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    candidate_path = Path(args.candidate)
    if not candidate_path.exists():
        print(json.dumps({"passed": False, "reasons": ["missing_candidate"]}, sort_keys=True))
        return 1
    try:
        data = json.loads(candidate_path.read_text(encoding="utf-8"))
    except ValueError:
        print(json.dumps({"passed": False, "reasons": ["candidate_unparseable"]}, sort_keys=True))
        return 1
    reasons: list[str] = []
    if not isinstance(data, dict):
        reasons.append("candidate_not_object")
    else:
        if type(data.get("final_value")) is not int:
            reasons.append("final_value_type")
        for key in ("evidence_ids", "rejected_stale_ids"):
            if not isinstance(data.get(key), list):
                reasons.append(f"{key}_type")
        if data.get("verifier_command") != VERIFIER:
            reasons.append("verifier_command_mismatch")
        trace = data.get("justification_trace")
        if not isinstance(trace, dict):
            reasons.append("justification_trace_type")
        else:
            ids = data.get("evidence_ids") if isinstance(data.get("evidence_ids"), list) else []
            ids = ids + (data.get("rejected_stale_ids") if isinstance(data.get("rejected_stale_ids"), list) else [])
            if any(not isinstance(trace.get(i), str) or len(trace[i].strip()) < 10 for i in ids):
                reasons.append("justification_short")
    result = {"passed": not reasons, "reason_codes": sorted(set(reasons))}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
