from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "tournament_stall_breaker.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("tournament_stall_breaker", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_escalates_after_three_no_progress_iterations() -> None:
    mod = _load_module()
    attempts = [
        {"target_gate": "1/2"},
        {"target_gate": "1/2"},
        {"target_gate": "1/2"},
        {"target_gate": "1/2"},
    ]
    result = mod.evaluate_target_gate_stall(attempts)
    assert result["stall_state"] == mod.STALL_STATE_ESCALATE
    assert result["recommended_action"] == mod.ACTION_FORCE_DIAGNOSTIC
    assert result["no_progress_iterations"] == 3
    assert result["best_target_gate_score"] == "1/2"


def test_blocks_after_five_no_progress_iterations() -> None:
    mod = _load_module()
    attempts = [{"target_gate": "1/2"} for _ in range(6)]
    result = mod.evaluate_target_gate_stall(attempts)
    assert result["stall_state"] == mod.STALL_STATE_BLOCKED
    assert result["recommended_action"] == mod.ACTION_PAUSE_BLOCKED
    assert result["no_progress_iterations"] == 5


def test_progress_resets_streak() -> None:
    mod = _load_module()
    attempts = [
        {"target_gate": "1/2"},
        {"target_gate": "1/2"},
        {"target_gate": "1/2"},
        {"target_gate": "2/2"},
        {"target_gate": "2/2"},
    ]
    result = mod.evaluate_target_gate_stall(attempts)
    assert result["stall_state"] == mod.STALL_STATE_ACTIVE
    assert result["recommended_action"] == mod.ACTION_CONTINUE
    assert result["no_progress_iterations"] == 1
    assert result["best_target_gate_score"] == "1/1"


def test_supports_dict_and_numeric_score_shapes() -> None:
    mod = _load_module()
    attempts = [
        {"best_target_gate_score": {"pass_count": "1", "total": "2"}},
        {"target_gate_score": 0.75},
        {"target_gate": "not-a-score"},
    ]
    result = mod.evaluate_target_gate_stall(attempts)
    assert result["stall_state"] == mod.STALL_STATE_ACTIVE
    assert result["recommended_action"] == mod.ACTION_CONTINUE
    assert result["best_target_gate_score"] == "3/4"
    assert result["parsed_attempt_count"] == 2
    assert result["ignored_attempt_indices"] == [2]


def test_returns_insufficient_signal_when_no_scores_parse() -> None:
    mod = _load_module()
    attempts = [{"target_gate": "bad"}, {"score": None}, {"note": "missing"}]
    result = mod.evaluate_target_gate_stall(attempts)
    assert result["stall_state"] == mod.STALL_STATE_INSUFFICIENT_SIGNAL
    assert result["recommended_action"] == mod.ACTION_CONTINUE
    assert result["parsed_attempt_count"] == 0
    assert result["no_progress_iterations"] == 0
