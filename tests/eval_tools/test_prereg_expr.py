"""Falsifier and promotion-bar expressions: parsing, truth values and rejection of malformed input."""

from __future__ import annotations

import pytest

from harness_evals.prereg_expr import ExpressionError, evaluate, parse

VALUES = {
    "baseline_rate": 0.5,
    "candidate_rate": 0.6,
    "diff": 0.1,
    "diff_ci_low": -0.05,
    "diff_ci_high": 0.3,
    "sentinel_regressions": 0.0,
}


def test_single_clause_follows_the_values():
    holds, clauses = evaluate("candidate_rate <= baseline_rate", VALUES)
    assert holds is False
    assert [clause.truth for clause in clauses] == [False]
    assert clauses[0].lhs_value == 0.6
    assert clauses[0].rhs_value == 0.5


def test_and_requires_every_clause_and_or_requires_one_group():
    assert evaluate("diff_ci_low > 0 and diff >= 0.05", VALUES)[0] is False
    assert evaluate("diff_ci_low > 0 and diff >= 0.05 or candidate_rate > 0.5", VALUES)[0] is True
    assert evaluate("diff_ci_low > 0 or diff >= 0.5", VALUES)[0] is False


def test_every_clause_is_reported_even_when_an_earlier_one_fails():
    _, clauses = evaluate("diff_ci_low > 0 and diff >= 0.05", VALUES)
    assert [clause.text for clause in clauses] == ["diff_ci_low > 0", "diff >= 0.05"]
    assert [clause.truth for clause in clauses] == [False, True]


def test_decimal_and_negative_literals_are_accepted():
    assert evaluate("diff_ci_low > -0.1", VALUES)[0] is True
    assert evaluate("diff == 0.1", VALUES)[0] is True


def test_parse_returns_or_of_and_groups():
    groups = parse("diff > 0 and diff < 1 or sentinel_regressions >= 1")
    assert [len(group) for group in groups] == [2, 1]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "diff >=",
        "diff =~ 0.1",
        "diff >= banana",
        "diff >= 1e3",
        "diff >= 0.1 and",
        "diff >= 0.1 and unknown_name > 0",
        "diff >= 0.1 xor diff < 1",
    ],
)
def test_malformed_expressions_are_rejected(text):
    with pytest.raises(ExpressionError):
        parse(text)


def test_missing_variable_value_is_an_error():
    partial = {key: value for key, value in VALUES.items() if key != "diff"}
    with pytest.raises(ExpressionError, match="diff"):
        evaluate("diff >= 0.1", partial)
