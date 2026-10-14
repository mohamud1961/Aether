"""Expressions for a pre-registered falsifier and promotion bar.

An expression is an OR of ANDs with no parentheses, for example
"candidate_rate <= baseline_rate" or "diff_ci_low > 0 and diff >= 0.10 or sentinel_regressions > 1".
Each clause is exactly three whitespace-separated tokens: operand, operator, operand. An operand is a
name from VARIABLES or a decimal literal such as 0.10. Evaluation compares floats. Nothing is passed to eval().
"""

from __future__ import annotations

import operator
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

VARIABLES = frozenset(
    {
        "baseline_rate",
        "candidate_rate",
        "diff",
        "diff_ci_low",
        "diff_ci_high",
        "sentinel_regressions",
    }
)
OPERATORS: dict[str, Callable[[float, float], bool]] = {
    "<=": operator.le,
    ">=": operator.ge,
    "==": operator.eq,
    "<": operator.lt,
    ">": operator.gt,
}
_LITERAL = re.compile(r"-?\d+(\.\d+)?")
_OR = re.compile(r"\s+or\s+")
_AND = re.compile(r"\s+and\s+")


class ExpressionError(ValueError):
    """An expression is malformed or names an unknown quantity."""


@dataclass(frozen=True)
class Clause:
    text: str
    lhs: str
    op: str
    rhs: str


@dataclass(frozen=True)
class ClauseResult:
    text: str
    lhs_value: float
    rhs_value: float
    truth: bool


def parse(text: str) -> tuple[tuple[Clause, ...], ...]:
    """Split an expression into OR groups, each a tuple of AND clauses. Raises ExpressionError."""
    stripped = text.strip()
    if not stripped:
        raise ExpressionError("expression is empty")
    return tuple(
        tuple(_clause(and_part) for and_part in _AND.split(or_part))
        for or_part in _OR.split(stripped)
    )


def evaluate(
    text: str, values: Mapping[str, float]
) -> tuple[bool, tuple[ClauseResult, ...]]:
    """Truth of the expression and the result of every clause. Every clause is evaluated for reporting."""
    truth = False
    results: list[ClauseResult] = []
    for group in parse(text):
        group_truth = True
        for clause in group:
            lhs_value = _operand(clause.lhs, values)
            rhs_value = _operand(clause.rhs, values)
            clause_truth = OPERATORS[clause.op](lhs_value, rhs_value)
            results.append(
                ClauseResult(clause.text, lhs_value, rhs_value, clause_truth)
            )
            group_truth = group_truth and clause_truth
        truth = truth or group_truth
    return truth, tuple(results)


def _clause(text: str) -> Clause:
    tokens = text.split()
    if len(tokens) != 3:
        raise ExpressionError(
            f"clause {text.strip()!r} must be 'operand operator operand'"
        )
    lhs, op, rhs = tokens
    if op not in OPERATORS:
        raise ExpressionError(
            f"unknown operator {op!r}; use one of {sorted(OPERATORS)}"
        )
    for operand in (lhs, rhs):
        if operand not in VARIABLES and not _LITERAL.fullmatch(operand):
            raise ExpressionError(
                f"unknown operand {operand!r}; variables are {sorted(VARIABLES)}"
            )
    return Clause(text=" ".join(tokens), lhs=lhs, op=op, rhs=rhs)


def _operand(token: str, values: Mapping[str, float]) -> float:
    if token in VARIABLES:
        if token not in values:
            raise ExpressionError(f"no value supplied for {token!r}")
        return float(values[token])
    return float(token)
