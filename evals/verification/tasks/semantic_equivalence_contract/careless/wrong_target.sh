#!/usr/bin/env bash
# expect: missing_solution_module
# Writes the legacy left-to-right evaluator, but to out/solution_v2.py rather than out/solution.py.
set -euo pipefail
mkdir -p out
cat > out/solution_v2.py <<'PY'
import re


def evaluate(expr: str) -> int:
    tokens = re.findall(r"[0-9]+|[+*-]", expr)
    value = int(tokens[0])
    for i in range(1, len(tokens), 2):
        op, number = tokens[i], int(tokens[i + 1])
        value = value + number if op == "+" else value - number if op == "-" else value * number
    return value
PY
