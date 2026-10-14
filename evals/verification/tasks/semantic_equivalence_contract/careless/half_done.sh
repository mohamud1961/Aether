#!/usr/bin/env bash
# expect: expression_evaluation_error
# Writes a recursive descent evaluator with the right precedence and left associativity, then stops before parentheses: any "(" raises.
set -euo pipefail
mkdir -p out
cat > out/solution.py <<'PY'
import re

_TOKEN = re.compile(r"[0-9]+|[()+*-]")


def evaluate(expr: str) -> int:
    tokens = _TOKEN.findall(expr)
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def take():
        nonlocal pos
        token = tokens[pos]
        pos += 1
        return token

    def term():
        value = factor()
        while peek() == "*":
            take()
            value = value * factor()
        return value

    def factor():
        token = take()
        if not token.isdigit():
            raise ValueError(f"unexpected token {token!r}")
        return int(token)

    def expr_level():
        value = term()
        while peek() in ("+", "-"):
            op = take()
            right = term()
            value = value + right if op == "+" else value - right
        return value

    return expr_level()
PY
