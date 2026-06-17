import json
from pathlib import Path


def evaluate(candidate_dir: Path, truth: dict) -> dict:
    report_path = candidate_dir / "fix_report.json"
    reasons = []
    passed = True

    if not report_path.exists():
        return {"passed": False, "score": 0.0, "reasons": ["missing_fix_report"]}

    data = json.loads(report_path.read_text())
    if bool(data.get("visible_tests_pass", False)) is not bool(truth["require_visible_tests_pass"]):
        passed = False
        reasons.append("visible_tests_not_passed")

    if bool(data.get("hidden_case_pass", False)) is not bool(truth["require_hidden_case_pass"]):
        passed = False
        reasons.append("hidden_case_not_resolved")

    if bool(data.get("regression_guard", False)) is not bool(truth["require_regression_guard"]):
        passed = False
        reasons.append("regression_guard_missing")

    if bool(data.get("final_verifier_rerun", False)) is not bool(truth["require_final_rerun"]):
        passed = False
        reasons.append("final_rerun_missing")

    return {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "reasons": reasons,
    }


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    truth = json.loads((root / "reviewer_pack" / "hidden_truth.json").read_text())
    result = evaluate(root / "candidate", truth)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
