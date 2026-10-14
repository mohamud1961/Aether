from __future__ import annotations

import json
import shutil

import pytest

from harness_evals.cli import main

pytestmark = pytest.mark.skipif(shutil.which("python3.11") is None, reason="python3.11 not on PATH")


def _run(example_task, agent: str, capsys) -> dict:
    assert main(["run-one", "--task", str(example_task), "--agent", agent]) == 0
    return json.loads(capsys.readouterr().out)


def test_reference_agent_applies_the_solution_and_passes(example_task, capsys):
    out = _run(example_task, "reference", capsys)
    assert out["task_id"] == "config_repair"
    assert out["agent"] == "reference"
    assert out["agent_result"]["finished"] is True
    assert out["agent_result"]["claim"] == "reference solution applied"
    assert out["agent_result"]["error"] is None
    assert out["grade"]["passed"] is True
    assert out["grade"]["score"] == 1.0
    assert out["grade"]["reasons"] == ["port_ok", "log_level_ok"]
    assert out["budget_s"] == 60.0


def test_noop_agent_changes_nothing_and_fails_grading(example_task, capsys):
    out = _run(example_task, "noop", capsys)
    assert out["agent_result"]["finished"] is False
    assert out["agent_result"]["claim"] == ""
    assert out["agent_result"]["tool_calls"] == 0
    assert out["grade"]["passed"] is False
    assert out["grade"]["reasons"] == ["port_not_integer_8080", "log_level_not_info"]


def test_unknown_agent_is_refused(example_task):
    from harness_evals.agents.base import UnknownAgent

    with pytest.raises(UnknownAgent, match="no agent named 'missing'"):
        main(["run-one", "--task", str(example_task), "--agent", "missing"])


def test_budget_must_be_positive(example_task):
    with pytest.raises(SystemExit):
        main(["run-one", "--task", str(example_task), "--agent", "noop", "--budget-s", "0"])


def test_reference_agent_rejects_options():
    from harness_evals.agents.reference import make

    with pytest.raises(TypeError, match="takes no options"):
        make(model="x")
