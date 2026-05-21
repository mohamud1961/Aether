#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-dir", default="candidate")
    args = parser.parse_args()

    candidate_dir = Path(args.candidate_dir).resolve()
    report_path = candidate_dir / "toolchain_repair_report.json"
    patch_list_path = candidate_dir / "patches_applied.txt"

    reasons = []
    if not report_path.exists():
        reasons.append("missing_toolchain_repair_report")
    if not patch_list_path.exists():
        reasons.append("missing_patches_applied")

    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("runner_command") != "python3 -m pytest tests/test_runner_contract.py -q":
            reasons.append("runner_command_mismatch")
        if report.get("package_manager") not in {"uv", "pip"}:
            reasons.append("unexpected_package_manager")
        if not bool(report.get("preflight_success", False)):
            reasons.append("preflight_not_successful")

    if patch_list_path.exists() and "scripts/run_tests.sh" not in patch_list_path.read_text(encoding="utf-8"):
        reasons.append("missing_required_patch_reference")

    result = {"passed": not reasons, "reason_codes": sorted(set(reasons))}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
