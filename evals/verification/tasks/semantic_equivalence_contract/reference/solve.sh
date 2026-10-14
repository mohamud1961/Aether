#!/usr/bin/env bash
# Writes out/solution.py: a recursive descent parser that follows spec/grammar_spec.md.
#   expr   := term (('+' | '-') term)*     left-associative
#   term   := factor ('*' factor)*
#   factor := '(' expr ')' | INTEGER
set -euo pipefail
mkdir -p out
cat > out/solution.py <<'PY'
"""Integer expression evaluator for the grammar in spec/grammar_spec.md."""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[0-9]+|[()+\-*]")


def _tokenize(text: str) -> list[str]:
    tokens = _TOKEN.findall(text)
    if "".join(tokens) != text:
        raise ValueError(f"unexpected character in {text!r}")
    return tokens


class _Parser:
    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> str | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _take(self) -> str:
        token = self._peek()
        if token is None:
            raise ValueError("unexpected end of expression")
        self._pos += 1
        return token

    def parse(self) -> int:
        value = self._expr()
        if self._peek() is not None:
            raise ValueError(f"unexpected token {self._peek()!r}")
        return value

    def _expr(self) -> int:
        value = self._term()
        while self._peek() in ("+", "-"):
            op = self._take()
            right = self._term()
            value = value + right if op == "+" else value - right
        return value

    def _term(self) -> int:
        value = self._factor()
        while self._peek() == "*":
            self._take()
            value = value * self._factor()
        return value

    def _factor(self) -> int:
        token = self._take()
        if token == "(":
            value = self._expr()
            if self._take() != ")":
                raise ValueError("expected ')'")
            return value
        if token.isdigit():
            return int(token)
        raise ValueError(f"unexpected token {token!r}")


def evaluate(expr: str) -> int:
    """Return the integer value of expr under the spec's precedence and associativity."""
    return _Parser(_tokenize(expr)).parse()
PY
