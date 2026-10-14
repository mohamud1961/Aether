#!/usr/bin/env bash
# expect: expression_result_mismatch
# Writes a single left-to-right level for + - *, as the legacy notes describe, so 2+3*4 gives 20.
set -euo pipefail
mkdir -p out
cat > out/solution.py <<'PY'
import re


def evaluate(expr: str) -> int:
    tokens = re.findall(r"[0-9]+|[()+*-]", expr)
    pos = 0

    def factor() -> int:
        nonlocal pos
        token = tokens[pos]
        pos += 1
        if token == "(":
            value = flat()
            pos += 1
            return value
        return int(token)

    def flat() -> int:
        nonlocal pos
        value = factor()
        while pos < len(tokens) and tokens[pos] in ("+", "-", "*"):
            op = tokens[pos]
            pos += 1
            right = factor()
            value = value + right if op == "+" else value - right if op == "-" else value * right
        return value

    return flat()
PY
