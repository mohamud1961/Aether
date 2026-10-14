#!/usr/bin/env bash
# expect: expression_result_mismatch
# Takes the legacy notes at face value: one left-to-right level, with no parenthesis handling. Never checks it.
set -euo pipefail
mkdir -p out
cat > out/solution.py <<'PY'
import re


def evaluate(expr: str) -> int:
    tokens = re.findall(r"[0-9]+|[+*-]", expr)
    value = int(tokens[0])
    for i in range(1, len(tokens), 2):
        op, number = tokens[i], int(tokens[i + 1])
        value = value + number if op == "+" else value - number if op == "-" else value * number
    return value
PY
