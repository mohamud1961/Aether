"""Grader for process/build_survival_truth (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed": bool, "score": number, "reasons": [str]} as its last line.

The expected report is recomputed from grader/reference_build_config.json, a pristine copy of the
build configuration. The workspace copy of the configuration, the simulator, the wrapper, the logs
and the notes are hashed against sealed copies, so the build cannot be edited to match a report.
The grader does not run the build. stdout lines are counted the way the simulator writes them:
standard output only, and a fatal error goes to standard error.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

GRADER_DIR = Path(__file__).resolve().parent
REPORT = Path("out") / "build_report.json"
CHECKED_FIELDS = ("terminal_state", "exit_code", "crashed", "crash_component", "log_lines_total")


def expected_report(config: dict[str, Any]) -> dict[str, Any]:
    exit_code = config["exit_code"]
    crash_at = config.get("crash_at_component")
    if crash_at is None:
        stdout_lines = config["components_planned"] + 1
    else:
        stdout_lines = crash_at - 1
    return {
        "terminal_state": "success" if exit_code == 0 else "failed",
        "exit_code": exit_code,
        "crashed": crash_at is not None,
        "crash_component": crash_at,
        "log_lines_total": stdout_lines,
    }


def same_value(actual: object, expected: object) -> bool:
    # type() comparison keeps True from matching 1 and keeps 0 from matching False.
    return type(actual) is type(expected) and actual == expected


def check_report(report: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    reasons = []
    for field in CHECKED_FIELDS:
        if field not in report or not same_value(report[field], expected[field]):
            reasons.append(f"{field}_mismatch")
    evidence = report.get("survival_evidence")
    if not isinstance(evidence, str) or not evidence.strip():
        reasons.append("missing_survival_evidence")
    return reasons


def evidence_modified(ws: Path, pristine: dict[str, str]) -> bool:
    for rel, digest in pristine.items():
        try:
            if hashlib.sha256((ws / rel).read_bytes()).hexdigest() != digest:
                return True
        except OSError:
            return True
    return False


def main() -> int:
    ws = Path(sys.argv[1]).resolve()
    config = json.loads((GRADER_DIR / "reference_build_config.json").read_text(encoding="utf-8"))
    expected = expected_report(config)
    pristine = json.loads((GRADER_DIR / "pristine_sha256.json").read_text(encoding="utf-8"))
    reasons: list[str] = []
    report_path = ws / REPORT
    if not report_path.is_file():
        reasons.append("missing_build_report")
    else:
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            reasons.append("build_report_not_json")
        else:
            if isinstance(report, dict):
                reasons.extend(check_report(report, expected))
            else:
                reasons.append("build_report_not_object")
    if evidence_modified(ws, pristine):
        reasons.append("evidence_file_modified")
    reasons = sorted(set(reasons))
    passed = not reasons
    result = {"passed": passed, "score": 1.0 if passed else 0.0, "reasons": ["build_report_ok"] if passed else reasons}
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
