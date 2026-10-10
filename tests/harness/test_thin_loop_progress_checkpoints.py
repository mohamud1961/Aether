"""Vertical, provider-free proofs for timed checkpoint integration in Thin."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aether.challenger_runtime.controller import ChallengerController
from aether.challenger_runtime.judge_client import JudgeClient
from aether.challenger_runtime.progress_checkpoint import (
    E2E_CHOICES, FOCUS_CHOICES, STAGE_CHOICES, TRACK_CHOICES,
)
from aether.envmap_builder import build_envmap_from_task
from aether.execution import CommandResult, MemoryExecutor
from aether.runtime_ir import ActionRequest, SolverTurn
import aether.thin_loop as thin_loop
from aether.thin_loop import ThinLoopConfig, run_thin_loop


TASK = "Update app.py and verify it runs."
STATE_DELTA = {
    "created_paths": [], "removed_paths": [], "content_changed_paths": [],
    "metadata_changed_paths": [], "before_truncated": False, "after_truncated": False,
    "mutation_detection_status": "complete", "path_set_delta_status": "complete",
}


def _action(kind: str, args: dict[str, Any], action_id: str) -> ActionRequest:
    return ActionRequest(
        action_id=action_id, kind=kind,
        capability_id="filesystem" if kind in {"write_file", "read_file"} else "shell",
        arguments=args, intent="inspect the current work", expected_observation="one exact result",
        if_fail_next="inspect the failure",
    )


def _packet(messages: list[dict[str, str]]) -> dict[str, Any]:
    marker = "[context_packet]\n"
    for message in messages:
        content = str(message.get("content", ""))
        if content.startswith(marker):
            return json.JSONDecoder().raw_decode(content[len(marker):])[0]
    raise AssertionError("Thin request omitted its context packet")


def _answers(request: dict[str, Any]) -> dict[str, Any]:
    picks = {
        "stage": STAGE_CHOICES[1],
        "end_to_end_run_exists": "unclear",
        "on_track_for_remaining_time": TRACK_CHOICES[1],
        "biggest_gap": "none",
        "recommended_focus": FOCUS_CHOICES[-1],
    }
    return {"answers": {
        key: {"choice": picks[key.removeprefix("progress_checkpoint:")], "confidence": 0.8}
        for key in request["questions"]
    }}


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now


class TimedSolver:
    def __init__(self, clock: FakeClock, times: tuple[float, ...], turns: tuple[SolverTurn, ...]) -> None:
        self.clock, self.times, self.turns = clock, times, turns
        self.requests: list[list[dict[str, str]]] = []

    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        index = len(self.requests)
        self.requests.append(json.loads(json.dumps(messages)))
        if index < len(self.times):
            self.clock.now = max(self.clock.now, self.times[index])
        return self.turns[index]


def _run(
    tmp_path: Path, monkeypatch, *, fractions: tuple[int, ...] | None,
    times: tuple[float, ...], turns: tuple[SolverTurn, ...], deadline: float | None = 100,
    files: dict[str, str] | None = None, cap_probe: list[dict[str, Any]] | None = None,
):
    clock = FakeClock()
    monkeypatch.setattr(thin_loop.time, "monotonic", clock.monotonic)
    progress_requests: list[dict[str, Any]] = []
    timeline: list[str] = []

    def progress(request: dict[str, Any]) -> dict[str, Any]:
        progress_requests.append(request)
        timeline.append(f"checkpoint:{request['state']['claim_card']['checkpoint_fraction_percent']}")
        if cap_probe is not None:
            cap_probe.append(request)
        return _answers(request)

    controller = None
    if fractions is not None:
        controller = ChallengerController(
            card_model=lambda _messages: "", evaluator=JudgeClient(
                lambda _request: {}, model="offline-fake", raw_task=TASK,
                progress_transport=progress,
            ), evidence_dir=tmp_path / "events", run_id="thin-loop-checkpoint", task_text=TASK,
            mode="challenger_v5", progress_fractions=fractions,
        )

    executor = MemoryExecutor(workspace_root="/app", files=files or {"app.py": "before"})
    def run_app(_executor: Any, command: str) -> CommandResult:
        timeline.append("tool:run_command:start")
        # Cross both later thresholds while the executor owns control. The loop
        # must wait until the following solver-turn boundary to ask either one.
        if cap_probe is None and progress_requests:
            clock.now = max(clock.now, 75.0)
            assert len(progress_requests) == 1
        timeline.append("tool:run_command:end")
        return CommandResult(command, 0, stdout="application started", state_delta=dict(STATE_DELTA))

    executor.register_command("python app.py", run_app)
    hooks = TimedSolver(clock, times, turns)
    env = build_envmap_from_task(
        "/tmp/aether-empty-task-dir", TASK, workspace_root="/app", projection_mode="factual_only",
    )
    result = run_thin_loop(env, executor, hooks, config=ThinLoopConfig(
        max_steps=len(turns), max_solver_turns=len(turns), visible_deadline_sec=deadline,
        run_started_monotonic=0.0,
        runtime_identity={"task_id": "fake", "run_id": "thin-loop-checkpoint", "primary_agent_id": "primary"},
        claim_ledger_controller=controller,
    ))
    return result, hooks, progress_requests, timeline, executor


def _turn(kind: str, args: dict[str, Any], name: str) -> SolverTurn:
    return SolverTurn(kind="act", summary=f"{kind} step", actions=(_action(kind, args, name),))


def test_real_thin_loop_fires_crossed_fractions_once_in_order_and_feedback_reaches_next_request(tmp_path, monkeypatch):
    turns = (
        _turn("write_file", {"path": "app.py", "content": "print('ready')"}, "write"),
        _turn("run_command", {"command": "python app.py"}, "run"),
        _turn("read_file", {"path": "app.py"}, "read-3"),
        _turn("read_file", {"path": "app.py"}, "read-4"),
        _turn("read_file", {"path": "app.py"}, "read-5"),
    )
    result, hooks, requests, timeline, _executor = _run(
        tmp_path, monkeypatch, fractions=(25, 50, 75, 90),
        times=(10, 25, 50, 75, 90), turns=turns,
    )

    assert len(requests) == 4
    assert [r["state"]["claim_card"]["checkpoint_fraction_percent"] for r in requests] == [25, 50, 75, 90]
    events = [json.loads(line) for line in (tmp_path / "events" / "challenger_events.jsonl").read_text().splitlines()]
    assert [e["fraction_percent"] for e in events if e["event"] == "progress_checkpoint"] == [25, 50, 75, 90]
    assert timeline.index("checkpoint:25") < timeline.index("tool:run_command:start")
    assert timeline.index("tool:run_command:start") < timeline.index("tool:run_command:end")
    assert timeline.index("tool:run_command:end") < timeline.index("checkpoint:50")
    # The solver's third invocation occurs after the 25% boundary and carries that advisory.
    third_packet = _packet(hooks.requests[2])
    assert "Progress check at 25% of time" in third_packet["claim_ledger_feedback"]["text"]
    assert "application started" in "\n".join(requests[1]["state"]["visible_evidence"].values())
    assert result.status == "step_budget_exhausted"


def test_real_thin_loop_50_only_and_no_deadline_suppresses_other_calls(tmp_path, monkeypatch):
    turns = tuple(_turn("read_file", {"path": "app.py"}, f"read-{n}") for n in range(3))
    _result, _hooks, requests, _timeline, _executor = _run(
        tmp_path / "only-50", monkeypatch, fractions=(50,), times=(25, 50, 90), turns=turns,
    )
    assert [r["state"]["claim_card"]["checkpoint_fraction_percent"] for r in requests] == [50]

    _result, _hooks, no_deadline, _timeline, _executor = _run(
        tmp_path / "no-deadline", monkeypatch, fractions=(25, 50, 75, 90),
        times=(25, 50, 75, 95), turns=turns + (_turn("read_file", {"path": "app.py"}, "read-4"),),
        deadline=None,
    )
    assert no_deadline == []


def test_control_requests_are_byte_identical_when_checkpoint_selector_is_off(tmp_path, monkeypatch):
    turns = (_turn("read_file", {"path": "app.py"}, "read"),)
    _, no_controller, *_ = _run(
        tmp_path / "control-a", monkeypatch, fractions=None, times=(0,), turns=turns,
        deadline=None,
    )
    _, empty_selector, *_ = _run(
        tmp_path / "control-b", monkeypatch, fractions=(), times=(0,), turns=turns,
        deadline=None,
    )
    assert no_controller.requests == empty_selector.requests
    assert json.dumps(no_controller.requests, sort_keys=True, separators=(",", ":")) == json.dumps(
        empty_selector.requests, sort_keys=True, separators=(",", ":"),
    )


def test_checkpoint_artifact_cap_trims_large_workspace_evidence(tmp_path, monkeypatch):
    requests: list[dict[str, Any]] = []
    turns = (
        _turn("write_file", {"path": "app.py", "content": "x" * 180_000}, "write-large-before-boundary"),
        _turn("read_file", {"path": "app.py"}, "read-at-boundary"),
    )
    _run(
        tmp_path, monkeypatch, fractions=(50,), times=(10, 50), turns=turns,
        files={"app.py": "x" * 180_000}, cap_probe=requests,
    )
    (request,) = requests
    encoded = json.dumps(request, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert len(encoded) <= 120_000
    visible = "\n".join(request["state"]["visible_evidence"].values())
    assert visible and len(visible) < 180_000
    assert request["state"]["raw_task"] == TASK and request["state"]["criteria"]
