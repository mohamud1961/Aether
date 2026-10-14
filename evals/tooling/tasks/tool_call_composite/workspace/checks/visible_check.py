#!/usr/bin/env python3
"""Readiness gate: checks that the candidate summary has its keys. It does not check values."""
import argparse
import json
from pathlib import Path

REQUIRED = ["tool_name", "ticket_id", "owner", "receipt_path", "verifier_command"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    path = Path(args.candidate)
    if not path.exists():
        print(json.dumps({"passed": False, "reason": "missing_candidate"}))
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED if key not in data]
    if missing:
        print(json.dumps({"passed": False, "missing": missing}, sort_keys=True))
        return 1
    print(json.dumps({"passed": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
