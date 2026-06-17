import json
from pathlib import Path


def evaluate(candidate_dir: Path, truth: dict) -> dict:
    manifest_path = candidate_dir / "patch_manifest.json"
    reasons = []
    passed = True

    if not manifest_path.exists():
        return {"passed": False, "score": 0.0, "reasons": ["missing_patch_manifest"]}

    data = json.loads(manifest_path.read_text())
    if data.get("target_file") != truth["expected_target_file"]:
        passed = False
        reasons.append("wrong_target_file")

    changed_files = data.get("changed_files", [])
    if not isinstance(changed_files, list) or len(changed_files) == 0:
        passed = False
        reasons.append("no_changed_files_recorded")

    for forbidden in truth["forbidden_touched_files"]:
        if forbidden in changed_files:
            passed = False
            reasons.append("forbidden_file_modified")

    if bool(data.get("verification_passed", False)) is not bool(truth["verification_must_pass"]):
        passed = False
        reasons.append("verification_not_confirmed")

    return {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "reasons": reasons,
    }


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    result = evaluate(root / "candidate", json.loads((root / "reviewer_pack" / "hidden_truth.json").read_text()))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
