"""Grader for the config_repair example task.

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line.
Reads only <workspace_dir>/config.json.
"""

import json
import sys
from pathlib import Path

# (ok reason, failing reason, field name, predicate on the field's value)
CHECKS = (
    ("port_ok", "port_not_integer_8080", "port", lambda value: type(value) is int and value == 8080),
    ("log_level_ok", "log_level_not_info", "log_level", lambda value: value == "info"),
)


def main() -> int:
    workspace = Path(sys.argv[1])
    try:
        config = json.loads((workspace / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(json.dumps({"passed": False, "score": 0.0, "reasons": ["config_not_json"]}, sort_keys=True))
        return 0
    if not isinstance(config, dict):
        print(json.dumps({"passed": False, "score": 0.0, "reasons": ["config_not_object"]}, sort_keys=True))
        return 0
    reasons = []
    passed_checks = 0
    for ok_reason, fail_reason, field, predicate in CHECKS:
        if predicate(config.get(field)):
            reasons.append(ok_reason)
            passed_checks += 1
        else:
            reasons.append(fail_reason)
    result = {
        "passed": passed_checks == len(CHECKS),
        "score": passed_checks / len(CHECKS),
        "reasons": reasons,
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
