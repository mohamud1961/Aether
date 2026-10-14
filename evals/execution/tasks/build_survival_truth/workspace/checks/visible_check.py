#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()

    candidate_path = Path(args.candidate).resolve()
    if not candidate_path.exists():
        print("missing candidate")
        return 1

    data = json.loads(candidate_path.read_text(encoding="utf-8"))
    required = [
        "terminal_state", "exit_code", "crashed",
        "crash_component", "log_lines_total", "survival_evidence",
    ]
    missing = [field for field in required if field not in data]
    reasons = []

    if missing:
        reasons.append(f"missing_fields: {missing}")

    if reasons:
        print(json.dumps({"passed": False, "reasons": reasons}, sort_keys=True))
        return 1

    print(json.dumps({"passed": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
