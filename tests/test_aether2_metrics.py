from __future__ import annotations

from dataclasses import asdict

import runner.aether2.metrics as metrics
from runner.aether2.metrics import Scorecard, build_scorecard


class SyntheticRun:
    pass


def test_build_scorecard_populates_required_fields():
    run = SyntheticRun()
    run.verifier_clean = True
    run.steps = 7
    run.model_calls = 5
    run.tokens_cached = 80
    run.tokens_fresh = 20
    run.cost = 1.25
    run.wall_time = 12.5
    run.no_delta_streaks = 3
    run.verification_rounds = 2
    run.recoveries = 1
    run.compaction_count = 4
    run.job_survival = True
    run.session_survival = False

    scorecard = build_scorecard(run)

    assert isinstance(scorecard, Scorecard)
    assert asdict(scorecard) == {
        "verifier_clean": True,
        "steps": 7,
        "model_calls": 5,
        "tokens_cached": 80,
        "tokens_fresh": 20,
        "cost": 1.25,
        "wall_time": 12.5,
        "cache_hit_ratio": 0.8,
        "no_delta_streaks": 3,
        "verification_rounds": 2,
        "recoveries": 1,
        "compaction_count": 4,
        "job_survival": True,
        "session_survival": False,
        "grader_reward": None,
        "action_type_breakdown": {},
    }
    assert scorecard.pass_ is True
    assert scorecard.as_dict()["verifier_clean"] is True
    assert scorecard.as_dict()["grader_reward"] is None


def test_build_scorecard_labels_tool_invocations_and_preserves_breakdown(monkeypatch):
    original = metrics.infer_action_type
    calls: list[tuple[str, str]] = []

    def spy(*, tool_name: str, command: str) -> str:
        calls.append((tool_name, command))
        return original(tool_name=tool_name, command=command)

    monkeypatch.setattr(metrics, "infer_action_type", spy)

    run = {
        "tokens_cached": 3,
        "tokens_fresh": 1,
        "tool_invocations": [
            {"tool_name": "register_service", "command": "launch"},
            {"tool_name": "probe_service", "command": "status"},
            {"tool_name": "read_file", "command": ""},
            {"tool_name": "raw_bash", "command": "python - <<'PY'\nprint('x')\nPY"},
            {"tool_name": "raw_bash", "command": "pytest tests/test_aether2_metrics.py"},
            {"tool_name": "raw_bash", "arguments": {"command": "echo hi"}},
        ],
    }

    scorecard = build_scorecard(run)

    assert calls == [
        ("register_service", "launch"),
        ("probe_service", "status"),
        ("read_file", ""),
        ("raw_bash", "python - <<'PY'\nprint('x')\nPY"),
        ("raw_bash", "pytest tests/test_aether2_metrics.py"),
        ("raw_bash", "echo hi"),
    ]
    assert scorecard.action_type_breakdown == {
        "command": 1,
        "native_tool_call": 1,
        "probe_service": 1,
        "script": 1,
        "start_service": 1,
        "verify": 1,
    }
    assert scorecard.as_dict()["action_type_breakdown"] == scorecard.action_type_breakdown
    assert scorecard.cache_hit_ratio == 0.75


def test_cache_hit_ratio_handles_zero_and_missing_tokens():
    zero = build_scorecard({})
    assert zero.cache_hit_ratio == 0.0

    run = {
        "tokens_cached": 3,
        "tokens_fresh": 1,
        "verifier_clean": False,
    }
    scorecard = build_scorecard(run)
    assert scorecard.cache_hit_ratio == 0.75
    assert scorecard.verifier_clean is False
    assert scorecard.pass_ is False
