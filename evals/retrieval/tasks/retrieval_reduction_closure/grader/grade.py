"""Grader for retrieval/retrieval_reduction_closure (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed": bool, "score": float, "reasons": [str]}.

Reads <workspace_dir>/out/final_submission.json and expected_truth.json beside this file.
The truth (counted and rejected IDs, the scalar, and the pristine hash of every input file)
is sealed with the grader, so an edited input file cannot move the target.
"""

import hashlib
import json
import sys
from pathlib import Path

REQUIRED_JUSTIFICATION_CHARS = 10
TOTAL_CHECKS = 6


def _emit(passed: bool, reasons: list[str]) -> int:
    score = 1.0 if passed else max(0.0, (TOTAL_CHECKS - len(reasons)) / TOTAL_CHECKS)
    print(json.dumps({"passed": passed, "score": score, "reasons": reasons}, sort_keys=True))
    return 0


def _is_int(value: object) -> bool:
    return type(value) is int


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    truth = json.loads(Path(__file__).with_name("expected_truth.json").read_text(encoding="utf-8"))

    input_reasons = [
        "input_file_modified"
        for rel, digest in sorted(truth["input_sha256"].items())
        if _sha256(workspace / rel) != digest
    ]

    candidate_path = workspace / "out" / "final_submission.json"
    if not candidate_path.is_file():
        return _emit(False, sorted(set(input_reasons + ["missing_candidate"])))
    try:
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _emit(False, sorted(set(input_reasons + ["candidate_json_invalid"])))
    if not isinstance(candidate, dict):
        return _emit(False, sorted(set(input_reasons + ["candidate_not_object"])))

    reasons: list[str] = list(input_reasons)
    if not (_is_int(candidate.get("final_value")) and candidate["final_value"] == truth["final_value"]):
        reasons.append("final_value_mismatch")
    if candidate.get("evidence_ids") != truth["active_ids"]:
        reasons.append("evidence_ids_mismatch")
    if candidate.get("rejected_stale_ids") != truth["stale_ids"]:
        reasons.append("stale_ids_mismatch")
    if candidate.get("verifier_command") != truth["verifier_command"]:
        reasons.append("verifier_command_mismatch")

    justification = candidate.get("justification_trace")
    if not isinstance(justification, dict):
        reasons.append("justification_trace_invalid")
    else:
        required_ids = list(truth["active_ids"]) + list(truth["stale_ids"])
        if any(
            not isinstance(justification.get(evidence_id), str)
            or len(justification[evidence_id].strip()) < REQUIRED_JUSTIFICATION_CHARS
            for evidence_id in required_ids
        ):
            reasons.append("justification_missing")

    unique = sorted(set(reasons))
    return _emit(not unique, unique)


if __name__ == "__main__":
    sys.exit(main())
