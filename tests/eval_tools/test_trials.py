from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest

from harness_evals import trials
from harness_evals.prereg import grader_hash
from harness_evals.agents.base import AgentResult
from harness_evals.agents.noop import make as make_noop
from harness_evals.agents.reference import make as make_reference
from harness_evals.sandbox import SandboxUnavailable
from harness_evals.task import Task, load_task, task_hash
from harness_evals.trials import (
    INVALID_AGENT_CRASH,
    INVALID_AGENT_ERROR,
    INVALID_GRADER_ERROR,
    INVALID_PROVIDER_ERROR,
    INVALID_RATE_LIMIT,
    INVALID_SANDBOX_FAILURE,
    INVALID_TIMEOUT_BEFORE_FIRST_ACTION,
    Arm,
    TrialFileError,
    TrialRow,
    classify_agent_result,
    read_rows,
    read_traces,
    run_trials,
    trace_path_for,
)


class ScriptedAgent:
    """Fake agent whose run() is a supplied function; counts how often it was called."""

    name = "scripted"

    def __init__(self, behaviour) -> None:  # type: ignore[no-untyped-def]
        self._behaviour = behaviour
        self.calls = 0

    def run(self, task: Task, sandbox, budget_s: float) -> AgentResult:  # type: ignore[no-untyped-def]
        self.calls += 1
        return self._behaviour(task, sandbox, budget_s)


def result(**overrides: object) -> AgentResult:
    values: dict[str, object] = {
        "finished": False,
        "claim": "",
        "tokens_in": 0,
        "tokens_out": 0,
        "cost": 0.0,
        "tool_calls": 0,
        "actions": [],
        "error": None,
        "trace": [],
    }
    values.update(overrides)
    return AgentResult(**values)  # type: ignore[arg-type]


def returning(**overrides: object):  # type: ignore[no-untyped-def]
    return lambda task, sandbox, budget_s: result(**overrides)


def arm_of(agent: object, name: str = "arm_a", version: str = "scripted-1") -> Arm:
    return Arm(name=name, agent=agent, version=version)  # type: ignore[arg-type]


def example() -> Task:
    return load_task(Path(__file__).resolve().parents[2] / "tests" / "eval_tools" / "fixtures" / "config_repair")


def run(tasks, arms, out: Path, **kwargs) -> list[TrialRow]:  # type: ignore[no-untyped-def]
    kwargs.setdefault("k", 1)
    kwargs.setdefault("sandbox_kind", "local")
    kwargs.setdefault("run_id", "run-test")
    return run_trials(tasks, arms, out_path=out, **kwargs)


def test_reference_agent_passes_the_example_task_on_every_attempt(tmp_path):
    task = example()
    out = tmp_path / "ref.jsonl"
    rows = run([task], [arm_of(make_reference(), "reference", "reference")], out, k=3)
    assert [row.attempt for row in rows] == [1, 2, 3]
    for row in rows:
        assert row.valid is True and row.invalid_reason is None
        assert row.passed is True and row.score == 1.0
        assert row.reasons == ("port_ok", "log_level_ok")
        assert row.tool_calls == 1 and row.repeated_actions == 0
        assert row.agent_version == "reference" and row.arm == "reference"
        assert row.task_hash == task_hash(task)
        assert row.grader_hash == grader_hash(task)
        assert row.prereg_hash is None
    assert read_rows(out) == rows


def test_noop_agent_on_the_example_task_is_a_valid_failure(tmp_path):
    rows = run([example()], [arm_of(make_noop(), "noop", "noop")], tmp_path / "noop.jsonl")
    (row,) = rows
    assert row.valid is True and row.invalid_reason is None
    assert row.passed is False
    assert row.reasons == ("port_not_integer_8080", "log_level_not_info")


def test_rows_and_traces_are_written_incrementally_and_keep_completed_rows_after_a_crash(tmp_path):
    out = tmp_path / "crash.jsonl"
    counter = {"calls": 0}

    def crash_on_second(task, sandbox, budget_s):  # type: ignore[no-untyped-def]
        counter["calls"] += 1
        if counter["calls"] == 2:
            raise KeyboardInterrupt
        return result()

    with pytest.raises(KeyboardInterrupt):
        run([example()], [arm_of(ScriptedAgent(crash_on_second))], out, k=2)
    assert [row.attempt for row in read_rows(out)] == [1]
    assert len(read_traces(trace_path_for(out))) == 1

    resumed = ScriptedAgent(returning())
    rows = run([example()], [arm_of(resumed)], out, k=2, resume=True)
    assert resumed.calls == 1
    assert [row.attempt for row in rows] == [1, 2]


def test_on_row_sees_each_row_already_on_disk(tmp_path):
    out = tmp_path / "callback.jsonl"
    seen: list[int] = []

    def check(row: TrialRow) -> None:
        seen.append(len(read_rows(out)))

    run([example()], [arm_of(ScriptedAgent(returning()))], out, k=3, on_row=check)
    assert seen == [1, 2, 3]


def test_resume_skips_completed_trials_and_runs_only_the_missing_attempts(tmp_path):
    out = tmp_path / "resume.jsonl"
    first = ScriptedAgent(returning())
    run([example()], [arm_of(first, "arm_a")], out, k=2)
    assert first.calls == 2

    second = ScriptedAgent(returning())
    rows = run([example()], [arm_of(second, "arm_a")], out, k=4, resume=True)
    assert second.calls == 2
    assert sorted(row.attempt for row in rows) == [1, 2, 3, 4]


def test_resume_does_not_rerun_invalid_trials(tmp_path):
    out = tmp_path / "invalid_resume.jsonl"
    limited = ScriptedAgent(returning(error="HTTP 429 rate limit exceeded"))
    first = run([example()], [arm_of(limited)], out, k=1)
    assert first[0].valid is False

    later = ScriptedAgent(returning())
    rows = run([example()], [arm_of(later)], out, k=1, resume=True)
    assert later.calls == 0
    assert [row.invalid_reason for row in rows] == [INVALID_RATE_LIMIT]


def test_resume_refuses_a_file_from_another_run(tmp_path):
    out = tmp_path / "other_run.jsonl"
    run([example()], [arm_of(ScriptedAgent(returning()))], out, run_id="run-a")
    with pytest.raises(ValueError, match="run-a"):
        run([example()], [arm_of(ScriptedAgent(returning()))], out, run_id="run-b", resume=True)


def test_existing_output_is_not_overwritten_without_resume(tmp_path):
    out = tmp_path / "exists.jsonl"
    run([example()], [arm_of(ScriptedAgent(returning()))], out)
    with pytest.raises(FileExistsError):
        run([example()], [arm_of(ScriptedAgent(returning()))], out)


def test_resume_repairs_a_partially_written_last_line(tmp_path):
    out = tmp_path / "partial.jsonl"
    run([example()], [arm_of(ScriptedAgent(returning()))], out, k=1)
    with out.open("a", encoding="utf-8") as handle:
        handle.write('{"run_id": "run-test", "arm": "arm_a", "tas')
    assert len(read_rows(out)) == 1
    rows = run([example()], [arm_of(ScriptedAgent(returning()))], out, k=2, resume=True)
    assert [row.attempt for row in rows] == [1, 2]
    assert len(out.read_text(encoding="utf-8").splitlines()) == 2


def test_a_malformed_line_in_the_middle_of_the_file_is_an_error(tmp_path):
    out = tmp_path / "corrupt.jsonl"
    out.write_text("not json\n", encoding="utf-8")
    with pytest.raises(TrialFileError, match="corrupt.jsonl:1"):
        read_rows(out)


def test_agent_exception_is_an_invalid_crash_and_the_run_continues(tmp_path):
    def explode(task, sandbox, budget_s):  # type: ignore[no-untyped-def]
        raise RuntimeError("agent exploded")

    out = tmp_path / "crash_agent.jsonl"
    crasher = ScriptedAgent(explode)
    rows = run([example()], [arm_of(crasher)], out, k=2)
    assert crasher.calls == 2
    assert [row.invalid_reason for row in rows] == [INVALID_AGENT_CRASH, INVALID_AGENT_CRASH]
    assert all(row.valid is False and row.passed is False for row in rows)
    trace = read_traces(trace_path_for(out))[("arm_a", "config_repair", 1)]
    assert trace.error == "RuntimeError: agent exploded"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("HTTP 429 from provider", INVALID_RATE_LIMIT),
        ("rate_limit exceeded", INVALID_RATE_LIMIT),
        ("provider returned status 503", INVALID_PROVIDER_ERROR),
        ("upstream connection reset by peer", INVALID_PROVIDER_ERROR),
        ("HTTP 500 Internal Server Error", INVALID_PROVIDER_ERROR),
        ("reference script exited with code 500", INVALID_AGENT_ERROR),
        ("tests could not start", INVALID_AGENT_ERROR),
    ],
)
def test_error_text_is_classified_into_the_invalid_taxonomy(error, expected):
    assert classify_agent_result(result(error=error, tool_calls=2), wall_s=1.0, budget_s=60.0) == expected


def test_timeout_before_the_first_action_is_invalid_but_a_timeout_after_work_is_an_ordinary_failure():
    idle = result(tool_calls=0)
    assert classify_agent_result(idle, wall_s=60.0, budget_s=60.0) == INVALID_TIMEOUT_BEFORE_FIRST_ACTION
    assert classify_agent_result(idle, wall_s=59.9, budget_s=60.0) is None
    worked = result(tool_calls=4)
    assert classify_agent_result(worked, wall_s=60.0, budget_s=60.0) is None


def test_timeout_before_first_action_is_classified_from_a_real_run(make_task, tmp_path):
    task = load_task(make_task(task_id="short", timeout_s=1))

    def stall(task, sandbox, budget_s):  # type: ignore[no-untyped-def]
        time.sleep(1.05)
        return result()

    (row,) = run([task], [arm_of(ScriptedAgent(stall))], tmp_path / "timeout.jsonl")
    assert row.valid is False
    assert row.invalid_reason == INVALID_TIMEOUT_BEFORE_FIRST_ACTION


def test_timeout_after_work_is_a_valid_failed_trial(make_task, tmp_path):
    task = load_task(make_task(task_id="short2", timeout_s=1))

    def slow_worker(task, sandbox, budget_s):  # type: ignore[no-untyped-def]
        time.sleep(1.05)
        return result(tool_calls=3, actions=["ls", "cat a", "make"])

    (row,) = run([task], [arm_of(ScriptedAgent(slow_worker))], tmp_path / "worked.jsonl")
    assert row.valid is True and row.invalid_reason is None
    assert row.passed is False


def test_agent_reported_error_after_work_is_an_invalid_agent_error(tmp_path):
    rows = run(
        [example()],
        [arm_of(ScriptedAgent(returning(tool_calls=3, error="tests could not start")))],
        tmp_path / "agent_error.jsonl",
    )
    assert [row.invalid_reason for row in rows] == [INVALID_AGENT_ERROR]


def test_sandbox_that_cannot_open_is_an_invalid_trial_and_the_agent_never_runs(tmp_path, monkeypatch):
    def unavailable(task, kind, **opts):  # type: ignore[no-untyped-def]
        raise SandboxUnavailable("docker daemon not reachable")

    monkeypatch.setattr(trials, "open_sandbox", unavailable)
    agent = ScriptedAgent(returning())
    rows = run([example()], [arm_of(agent)], tmp_path / "sandbox.jsonl", k=2)
    assert agent.calls == 0
    assert [row.invalid_reason for row in rows] == [INVALID_SANDBOX_FAILURE, INVALID_SANDBOX_FAILURE]
    assert all(row.passed is False and row.valid is False for row in rows)


def test_grader_that_breaks_its_contract_is_an_invalid_trial(make_task, tmp_path):
    task = load_task(make_task(task_id="bad_grader", grader="print('not json')\n"))
    (row,) = run([task], [arm_of(make_noop(), "noop")], tmp_path / "grader.jsonl")
    assert row.valid is False
    assert row.invalid_reason == INVALID_GRADER_ERROR
    assert row.passed is False and row.score == 0.0


def test_repeated_actions_are_counted_and_the_trace_sidecar_keeps_the_actions(tmp_path):
    actions = ["ls", "ls", "ls", "cat config.json"]
    out = tmp_path / "actions.jsonl"
    run(
        [example()],
        [arm_of(ScriptedAgent(returning(tool_calls=4, actions=actions, trace=[{"step": 1}])))],
        out,
    )
    (row,) = read_rows(out)
    assert row.repeated_actions == 3
    assert row.tool_calls == 4
    trace = read_traces(trace_path_for(out))[("arm_a", "config_repair", 1)]
    assert list(trace.actions) == actions
    assert [dict(item) for item in trace.trace] == [{"step": 1}]


def test_tokens_cost_and_agent_version_come_from_the_agent_result(tmp_path):
    out = tmp_path / "tokens.jsonl"
    run(
        [example()],
        [arm_of(ScriptedAgent(returning(tokens_in=120, tokens_out=40, cost=0.0123, tool_calls=2)), "m", "minimal:x")],
        out,
        prereg_hash="abc123",
    )
    (row,) = read_rows(out)
    assert (row.tokens_in, row.tokens_out, row.cost) == (120, 40, 0.0123)
    assert row.arm == "m" and row.agent_version == "minimal:x"
    assert row.prereg_hash == "abc123"


def test_arms_and_tasks_run_in_arm_then_task_order(make_task, tmp_path):
    second = load_task(make_task(task_id="second"))
    rows = run(
        [example(), second],
        [arm_of(make_reference(), "ref", "reference"), arm_of(make_noop(), "noop", "noop")],
        tmp_path / "order.jsonl",
        k=2,
    )
    assert [(row.arm, row.task_id, row.attempt) for row in rows] == [
        ("ref", "config_repair", 1),
        ("ref", "config_repair", 2),
        ("ref", "second", 1),
        ("ref", "second", 2),
        ("noop", "config_repair", 1),
        ("noop", "config_repair", 2),
        ("noop", "second", 1),
        ("noop", "second", 2),
    ]


def test_invalid_inputs_are_refused_before_anything_runs(tmp_path):
    out = tmp_path / "refused.jsonl"
    arm = arm_of(ScriptedAgent(returning()))
    with pytest.raises(ValueError, match="k must be"):
        run([example()], [arm], out, k=0)
    with pytest.raises(ValueError, match="unique"):
        run([example()], [arm, arm_of(ScriptedAgent(returning()))], out)
    with pytest.raises(ValueError, match="sandbox kind"):
        run([example()], [arm], out, sandbox_kind="vm")
    with pytest.raises(ValueError, match="no tasks"):
        run([], [arm], out)
    assert not out.exists()


def test_task_hash_in_rows_changes_when_a_task_file_changes(make_task, tmp_path):
    task_dir = make_task(task_id="hashed")
    task = load_task(task_dir)
    before = run([task], [arm_of(make_noop(), "noop")], tmp_path / "h1.jsonl")[0].task_hash
    (task_dir / "prompt.md").write_text("A different prompt.\n", encoding="utf-8")
    after = run([load_task(task_dir)], [arm_of(make_noop(), "noop")], tmp_path / "h2.jsonl")[0].task_hash
    assert before != after


def test_trial_row_round_trips_through_json():
    row = TrialRow(
        run_id="r",
        arm="a",
        task_id="t",
        attempt=1,
        started_at="2026-10-13T00:00:00+00:00",
        wall_s=0.5,
        passed=True,
        score=1.0,
        reasons=("ok",),
        valid=True,
        invalid_reason=None,
        tokens_in=1,
        tokens_out=2,
        cost=0.25,
        tool_calls=3,
        repeated_actions=0,
        agent_version="v",
        grader_hash="g",
        task_hash="h",
        prereg_hash=None,
    )
    assert TrialRow.from_dict(json.loads(row.to_json())) == row


def test_a_row_with_a_missing_field_is_refused():
    with pytest.raises(TrialFileError, match="keys differ"):
        TrialRow.from_dict({"run_id": "r"})
