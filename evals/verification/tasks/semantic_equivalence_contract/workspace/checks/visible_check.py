#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def main() -> int:
    solution_path = Path(__file__).resolve().parents[1] / "out" / "solution.py"
    if not solution_path.exists():
        print(json.dumps({"passed": False, "reasons": ["missing out/solution.py"]}, sort_keys=True))
        return 1

    sys.path.insert(0, str(solution_path.parent))
    try:
        from solution import evaluate
    except ImportError as exc:
        print(json.dumps({"passed": False, "reasons": [f"import_error: {exc}"]}, sort_keys=True))
        return 1

    simple_cases = [("1+2", 3), ("3*4", 12), ("10-5", 5)]
    failures = []
    for expr, expected in simple_cases:
        try:
            result = evaluate(expr)
            if result != expected:
                failures.append(f"{expr}: expected {expected}, got {result}")
        except Exception as exc:
            failures.append(f"{expr}: raised {exc}")

    if failures:
        print(json.dumps({"passed": False, "reasons": failures}, sort_keys=True))
        return 1

    print(json.dumps({"passed": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
