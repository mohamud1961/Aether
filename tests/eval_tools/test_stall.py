"""Stall-detection tests. Ported assertions; the source tree had no direct test for this module."""

from __future__ import annotations

from harness_evals.stall import evaluate_target_gate_stall


def _attempts(*gates):
    return [{"target_gate": g} for g in gates]


def test_no_parseable_scores_is_insufficient_signal():
    result = evaluate_target_gate_stall([{"note": "no score"}])
    assert result["stall_state"] == "insufficient_signal"
    assert result["recommended_action"] == "continue"
    assert result["ignored_attempt_indices"] == [0]


def test_improving_attempts_stay_active():
    result = evaluate_target_gate_stall(_attempts("1/4", "2/4", "3/4"))
    assert result["stall_state"] == "active"
    assert result["no_progress_iterations"] == 0
    assert result["best_target_gate_score"] == "3/4"


def test_three_non_improving_attempts_escalate_to_forced_diagnostic():
    result = evaluate_target_gate_stall(_attempts("2/4", "2/4", "1/4", "2/4"))
    assert result["no_progress_iterations"] == 3
    assert result["stall_state"] == "escalate"
    assert result["recommended_action"] == "force_diagnostic"


def test_five_non_improving_attempts_block():
    result = evaluate_target_gate_stall(_attempts("1/2", "1/2", "1/2", "1/2", "1/2", "1/2"))
    assert result["no_progress_iterations"] == 5
    assert result["stall_state"] == "blocked"
    assert result["recommended_action"] == "pause_blocked"


def test_progress_resets_the_streak():
    result = evaluate_target_gate_stall(_attempts("1/2", "1/2", "1/2", "3/4", "3/4"))
    assert result["no_progress_iterations"] == 1
    assert result["stall_state"] == "active"


def test_equal_fraction_is_not_progress():
    # 2/4 == 1/2 as a value; a tie is not an improvement
    result = evaluate_target_gate_stall(_attempts("1/2", "2/4"))
    assert result["no_progress_iterations"] == 1


def test_dict_and_numeric_scores_are_parsed():
    result = evaluate_target_gate_stall([
        {"target_gate": {"pass_count": 1, "total": 2}},
        {"best_target_gate_score": 0.75},
    ])
    assert result["parsed_attempt_count"] == 2
    assert result["best_target_gate_score"] == "3/4"
