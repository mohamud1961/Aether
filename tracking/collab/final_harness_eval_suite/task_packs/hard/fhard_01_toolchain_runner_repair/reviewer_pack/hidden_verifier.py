import json
from pathlib import Path


def evaluate(candidate_dir: Path, truth: dict) -> dict:
    report_path = candidate_dir / "toolchain_repair_report.json"
    patch_list_path = candidate_dir / "patches_applied.txt"
    reasons = []
    passed = True

    if not report_path.exists():
        return {"passed": False, "score": 0.0, "reasons": ["missing_report"]}

    data = json.loads(report_path.read_text())
    if data.get("runner_command") != truth["expected_runner_command"]:
        passed = False
        reasons.append("runner_command_mismatch")

    if data.get("package_manager") not in truth["allowed_package_managers"]:
        passed = False
        reasons.append("package_manager_invalid")

    if not data.get("preflight_success", False):
        passed = False
        reasons.append("preflight_not_successful")

    evidence = data.get("evidence", [])
    if not isinstance(evidence, list) or len(evidence) < 2:
        passed = False
        reasons.append("insufficient_evidence")

    if not patch_list_path.exists():
        passed = False
        reasons.append("missing_patch_list")
    else:
        patch_text = patch_list_path.read_text()
        if truth["required_patch_reference"] not in patch_text:
            passed = False
            reasons.append("required_patch_not_recorded")

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
