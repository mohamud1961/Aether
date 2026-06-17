import json
from pathlib import Path


def evaluate(candidate_dir: Path, truth: dict) -> dict:
    receipt_path = candidate_dir / "readiness_receipt.json"
    reasons = []
    passed = True

    if not receipt_path.exists():
        return {"passed": False, "score": 0.0, "reasons": ["missing_readiness_receipt"]}

    data = json.loads(receipt_path.read_text())
    expected_suffix = f":{truth['expected_port']}/healthz"
    if not str(data.get("service_url", "")).endswith(expected_suffix):
        passed = False
        reasons.append("wrong_service_port_or_route")

    if int(data.get("probes_passed", 0)) < int(truth["minimum_probe_count"]):
        passed = False
        reasons.append("insufficient_probe_count")

    if bool(data.get("wrong_port_rejected", False)) is not bool(truth["require_wrong_port_rejection"]):
        passed = False
        reasons.append("wrong_port_rejection_missing")

    if bool(data.get("cleanup_performed", False)) is not bool(truth["require_cleanup"]):
        passed = False
        reasons.append("cleanup_not_confirmed")

    return {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "reasons": reasons,
    }


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    candidate_dir = root / "candidate"
    truth = json.loads((root / "reviewer_pack" / "hidden_truth.json").read_text())
    result = evaluate(candidate_dir, truth)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
