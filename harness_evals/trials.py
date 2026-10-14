"""Trials: run arms x tasks x attempts, grade each attempt, classify validity and write trial rows.

A trial is one agent attempt on one task in a fresh sandbox, graded by the task's hidden grader.
Each finished trial is appended to the output JSONL and fsynced before the next trial starts, so a
crash keeps every completed row. A sidecar file next to it (`<stem>.traces.jsonl`) holds each
trial's actions, error and the agent's trace, which trajectory analysis reads.

Validity. A trial is invalid when the measurement did not happen:
- sandbox_failure: the sandbox could not be opened (no agent ran);
- agent_crash: the agent raised an exception;
- rate_limit / provider_error: the agent reported a rate-limit or provider failure;
- timeout_before_first_action: no tool call was made and the budget was used up;
- agent_error: the agent reported any other error;
- grader_error: the grader broke its output contract or could not run.
Invalid rows are kept with invalid_reason set; the report excludes them from rates. An ordinary
failure (the grader says the state is wrong) is a valid failed trial.

Resume. A (arm, task, attempt) that already has a row, valid or invalid, is not run again.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness_evals.agents.base import Agent, AgentResult
from harness_evals.trial_io import (
    TrialFileError,
    _read_jsonl,
    _append_line,
    _trim_partial_tail,
)
from harness_evals.grading import GradeResult, grade
from harness_evals.sandbox import Sandbox, SandboxUnavailable, open_sandbox
from harness_evals.task import Task, task_hash
from harness_evals.prereg import grader_hash as grader_bundle_hash
from harness_evals.trajectory import count_repeated_actions

INVALID_SANDBOX_FAILURE = "sandbox_failure"
INVALID_AGENT_CRASH = "agent_crash"
INVALID_RATE_LIMIT = "rate_limit"
INVALID_PROVIDER_ERROR = "provider_error"
INVALID_TIMEOUT_BEFORE_FIRST_ACTION = "timeout_before_first_action"
INVALID_AGENT_ERROR = "agent_error"
INVALID_GRADER_ERROR = "grader_error"
INVALID_REASONS: tuple[str, ...] = (
    INVALID_SANDBOX_FAILURE,
    INVALID_AGENT_CRASH,
    INVALID_RATE_LIMIT,
    INVALID_PROVIDER_ERROR,
    INVALID_TIMEOUT_BEFORE_FIRST_ACTION,
    INVALID_AGENT_ERROR,
    INVALID_GRADER_ERROR,
)

TRACE_SUFFIX = ".traces.jsonl"
SANDBOX_KINDS = ("local", "docker")

_RATE_LIMIT = re.compile(
    r"rate[ _-]?limit|too many requests|(?:http|status|error)\D{0,10}429\b",
    re.IGNORECASE,
)
_PROVIDER = re.compile(
    r"provider|api error|overloaded|service unavailable|bad gateway|connection (?:reset|refused|error)"
    r"|(?:http|status|error)\D{0,10}5\d\d\b",
    re.IGNORECASE,
)

TrialKey = tuple[str, str, int]


@dataclass(frozen=True)
class Arm:
    """One configuration under test. name labels rows; version records what ran (e.g. agent and model)."""

    name: str
    agent: Agent
    version: str


@dataclass(frozen=True)
class TrialRow:
    run_id: str
    arm: str
    task_id: str
    attempt: int
    started_at: str
    wall_s: float
    passed: bool
    score: float
    reasons: tuple[str, ...]
    valid: bool
    invalid_reason: str | None
    tokens_in: int
    tokens_out: int
    cost: float
    tool_calls: int
    repeated_actions: int
    agent_version: str
    grader_hash: str
    task_hash: str
    prereg_hash: str | None

    @property
    def key(self) -> TrialKey:
        return (self.arm, self.task_id, self.attempt)

    def to_json(self) -> str:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return json.dumps(data, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TrialRow:
        expected = {item.name for item in fields(cls)}
        if set(data) != expected:
            raise TrialFileError(
                f"trial row keys differ: {sorted(set(data) ^ expected)}"
            )
        values = dict(data)
        values["reasons"] = tuple(data["reasons"])
        return cls(**values)


@dataclass(frozen=True)
class TrialTrace:
    run_id: str
    arm: str
    task_id: str
    attempt: int
    error: str | None
    actions: tuple[str, ...]
    trace: tuple[dict[str, Any], ...]

    @property
    def key(self) -> TrialKey:
        return (self.arm, self.task_id, self.attempt)

    def to_json(self) -> str:
        data = asdict(self)
        data["actions"] = list(self.actions)
        data["trace"] = list(self.trace)
        return json.dumps(data, sort_keys=True, default=str)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TrialTrace:
        return cls(
            run_id=data["run_id"],
            arm=data["arm"],
            task_id=data["task_id"],
            attempt=data["attempt"],
            error=data["error"],
            actions=tuple(data["actions"]),
            trace=tuple(data["trace"]),
        )


@dataclass(frozen=True)
class _Digests:
    task: str
    grader: str


@dataclass(frozen=True)
class _Outcome:
    agent: AgentResult | None
    crash: str | None
    sandbox_error: str | None
    wall_s: float
    graded: GradeResult | None


def classify_agent_result(
    result: AgentResult, wall_s: float, budget_s: float
) -> str | None:
    """Invalid reason for an agent that returned normally, or None when the trial measured something."""
    if result.error is not None:
        if _RATE_LIMIT.search(result.error):
            return INVALID_RATE_LIMIT
        if _PROVIDER.search(result.error):
            return INVALID_PROVIDER_ERROR
    if result.tool_calls == 0 and wall_s >= budget_s:
        return INVALID_TIMEOUT_BEFORE_FIRST_ACTION
    if result.error is not None:
        return INVALID_AGENT_ERROR
    return None


def trace_path_for(out_path: Path) -> Path:
    return out_path.with_name(out_path.stem + TRACE_SUFFIX)


def existing_run_id(out_path: Path) -> str | None:
    """The run id held by an existing rows file, or None when the file is absent or empty."""
    run_ids = (
        {row.run_id for row in read_rows(out_path)}
        if Path(out_path).exists()
        else set()
    )
    if len(run_ids) > 1:
        raise ValueError(f"{out_path} holds more than one run id: {sorted(run_ids)}")
    return run_ids.pop() if run_ids else None


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:6]}"


def run_trials(
    tasks: Sequence[Task],
    arms: Sequence[Arm],
    k: int,
    sandbox_kind: str,
    out_path: Path,
    run_id: str,
    *,
    resume: bool = False,
    prereg_hash: str | None = None,
    on_row: Callable[[TrialRow], None] | None = None,
) -> list[TrialRow]:
    """Run every (arm, task, attempt) not yet in out_path and return all rows in the file, in order."""
    _check_inputs(tasks, arms, k, sandbox_kind)
    out_path = Path(out_path)
    traces_path = trace_path_for(out_path)
    existing = _load_existing(out_path, traces_path, run_id, resume)
    done = {row.key for row in existing}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    digests = {
        task.id: _Digests(task=task_hash(task), grader=grader_bundle_hash(task))
        for task in tasks
    }
    # Refuse changed versions/source rather than treating old rows as a fresh run.
    selected_arms = {arm.name: arm for arm in arms}
    for row in existing:
        if row.arm in selected_arms and row.task_id in digests:
            current = digests[row.task_id]
            if (
                row.task_hash != current.task
                or row.grader_hash != current.grader
                or row.agent_version != selected_arms[row.arm].version
                or row.prereg_hash != prereg_hash
            ):
                raise ValueError("resume source/config drift")
    rows = list(existing)
    for arm in arms:
        for task in tasks:
            for attempt in range(1, k + 1):
                if (arm.name, task.id, attempt) in done:
                    continue
                row, trace = _attempt(
                    arm,
                    task,
                    attempt,
                    run_id,
                    sandbox_kind,
                    digests[task.id],
                    prereg_hash,
                )
                _append_line(out_path, row.to_json())
                _append_line(traces_path, trace.to_json())
                rows.append(row)
                if on_row is not None:
                    on_row(row)
    return rows


def read_rows(path: Path) -> list[TrialRow]:
    return [TrialRow.from_dict(record) for record in _read_jsonl(path)]


def read_traces(path: Path) -> dict[TrialKey, TrialTrace]:
    """Traces keyed by trial. When a trial was written twice (a crash between the two files), the last wins."""
    traces = [TrialTrace.from_dict(record) for record in _read_jsonl(path)]
    return {trace.key: trace for trace in traces}


def _check_inputs(
    tasks: Sequence[Task], arms: Sequence[Arm], k: int, sandbox_kind: str
) -> None:
    if not tasks:
        raise ValueError("no tasks to run")
    if not arms:
        raise ValueError("no arms to run")
    names = [arm.name for arm in arms]
    if len(set(names)) != len(names):
        raise ValueError(f"arm names must be unique, got {names}")
    if len({task.id for task in tasks}) != len(tasks):
        raise ValueError("task ids must be unique")
    if k < 1:
        raise ValueError("k must be at least 1")
    if sandbox_kind not in SANDBOX_KINDS:
        raise ValueError(
            f"unknown sandbox kind {sandbox_kind!r}; expected one of {SANDBOX_KINDS}"
        )


def _load_existing(
    out_path: Path, traces_path: Path, run_id: str, resume: bool
) -> list[TrialRow]:
    if not resume:
        for path in (out_path, traces_path):
            if path.exists():
                raise FileExistsError(
                    f"{path} already exists; pass resume to continue it or choose a new output"
                )
        return []
    if not out_path.exists():
        if traces_path.exists():
            raise ValueError(
                f"{traces_path} exists without {out_path}; remove it or choose a new output"
            )
        return []
    _trim_partial_tail(out_path)
    _trim_partial_tail(traces_path)
    rows = read_rows(out_path)
    foreign = sorted({row.run_id for row in rows} - {run_id})
    if foreign:
        raise ValueError(f"{out_path} holds rows from run(s) {foreign}, not {run_id!r}")
    if rows:
        traces = read_traces(traces_path)
        if any(row.key not in traces for row in rows):
            raise ValueError(
                "incomplete evidence: a completed row is missing its trace"
            )
    return rows


def _attempt(
    arm: Arm,
    task: Task,
    attempt: int,
    run_id: str,
    sandbox_kind: str,
    digests: _Digests,
    prereg_hash: str | None,
) -> tuple[TrialRow, TrialTrace]:
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    outcome = _execute(arm.agent, task, sandbox_kind)
    budget_s = float(task.timeout_s)
    reason = _invalid_reason(outcome, budget_s)
    agent = outcome.agent
    actions = list(agent.actions) if agent is not None else []
    graded = outcome.graded
    row = TrialRow(
        run_id=run_id,
        arm=arm.name,
        task_id=task.id,
        attempt=attempt,
        started_at=started_at,
        wall_s=round(outcome.wall_s, 3),
        passed=graded.passed if graded is not None else False,
        score=graded.score if graded is not None else 0.0,
        reasons=graded.reasons if graded is not None else (),
        valid=reason is None,
        invalid_reason=reason,
        tokens_in=agent.tokens_in if agent is not None else 0,
        tokens_out=agent.tokens_out if agent is not None else 0,
        cost=agent.cost if agent is not None else 0.0,
        tool_calls=agent.tool_calls if agent is not None else 0,
        repeated_actions=count_repeated_actions(actions),
        agent_version=arm.version,
        grader_hash=digests.grader,
        task_hash=digests.task,
        prereg_hash=prereg_hash,
    )
    trace = TrialTrace(
        run_id=run_id,
        arm=arm.name,
        task_id=task.id,
        attempt=attempt,
        error=_first_error(outcome),
        actions=tuple(actions),
        trace=tuple(agent.trace) if agent is not None else (),
    )
    return row, trace


def _execute(agent: Agent, task: Task, sandbox_kind: str) -> _Outcome:
    if task.admission == "debug" and agent.name not in {"reference", "noop"}:
        return _Outcome(
            agent=None,
            crash=None,
            sandbox_error="isolated candidate-execution grader unavailable",
            wall_s=0.0,
            graded=None,
        )
    try:
        sandbox = open_sandbox(task, sandbox_kind, trusted=agent.name == "reference")
    except (SandboxUnavailable, OSError) as exc:
        return _Outcome(
            agent=None, crash=None, sandbox_error=str(exc), wall_s=0.0, graded=None
        )
    try:
        result, crash, wall_s = _call_agent(agent, task, sandbox)
        graded = _grade_safely(task, sandbox.root)
    finally:
        sandbox.close()
    return _Outcome(
        agent=result, crash=crash, sandbox_error=None, wall_s=wall_s, graded=graded
    )


def _call_agent(
    agent: Agent, task: Task, sandbox: Sandbox
) -> tuple[AgentResult | None, str | None, float]:
    start = time.monotonic()
    try:
        result = agent.run(task, sandbox, float(task.timeout_s))
    except (
        Exception
    ) as exc:  # recorded as an invalid trial; one crash never aborts the run
        return None, f"{type(exc).__name__}: {exc}", time.monotonic() - start
    return result, None, time.monotonic() - start


def _grade_safely(task: Task, root: Path) -> GradeResult:
    try:
        return grade(task, root, timeout_s=task.timeout_s)
    except Exception as exc:  # grade() reports contract problems itself; this guards unexpected failures
        return GradeResult(
            passed=False,
            score=0.0,
            reasons=(),
            grader_hash=_sha256_file(task.grader_path),
            error=f"grading raised {type(exc).__name__}: {exc}",
        )


def _invalid_reason(outcome: _Outcome, budget_s: float) -> str | None:
    if outcome.sandbox_error is not None:
        return INVALID_SANDBOX_FAILURE
    if outcome.agent is None:
        return INVALID_AGENT_CRASH
    reason = classify_agent_result(outcome.agent, outcome.wall_s, budget_s)
    if (
        reason is None
        and outcome.graded is not None
        and outcome.graded.error is not None
    ):
        return INVALID_GRADER_ERROR
    return reason


def _first_error(outcome: _Outcome) -> str | None:
    if outcome.sandbox_error is not None:
        return outcome.sandbox_error
    if outcome.crash is not None:
        return outcome.crash
    if outcome.agent is not None and outcome.agent.error is not None:
        return outcome.agent.error
    if outcome.graded is not None:
        return outcome.graded.error
    return None


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
