#!/usr/bin/env python3
"""Readiness gate: checks the candidate's keys and types only (NOT the values)."""
import argparse
import json
from pathlib import Path

REQUIRED = {
    "schema_version": str,
    "files_changed": list,
    "visible_tests_pass": bool,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    path = Path(args.candidate)
    if not path.exists():
        print(json.dumps({"passed": False, "reasons": ["missing_candidate"]}, sort_keys=True))
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        print(json.dumps({"passed": False, "reasons": ["candidate_unparseable"]}, sort_keys=True))
        return 1
    reasons = []
    if not isinstance(data, dict):
        reasons.append("candidate_not_object")
    else:
        for key, kind in REQUIRED.items():
            if type(data.get(key)) is not kind:
                reasons.append(f"{key}_type")
    result = {"passed": not reasons, "reason_codes": sorted(set(reasons))}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
