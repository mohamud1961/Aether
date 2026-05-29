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
    required = ["final_value", "evidence_ids", "rejected_stale_ids", "justification_trace"]
    missing = [field for field in required if field not in data]
    reasons = []

    if missing:
        reasons.append(f"missing_fields: {missing}")
    else:
        trace = data.get("justification_trace", {})
        if not isinstance(trace, dict):
            reasons.append("justification_trace_not_dict")
        else:
            all_ids = data.get("evidence_ids", []) + data.get("rejected_stale_ids", [])
            missing_justifications = [i for i in all_ids if i not in trace]
            if missing_justifications:
                reasons.append(f"missing_justifications_for_ids: {missing_justifications}")

    if reasons:
        print(json.dumps({"passed": False, "reasons": reasons}, sort_keys=True))
        return 1

    print(json.dumps({"passed": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
