"""Behavioral checks for the timed CHALLENGER advisory checkpoint request."""
from __future__ import annotations

import json

import pytest

from aether.challenger_runtime.controller import ChallengerController
from aether.challenger_runtime.progress_checkpoint import (
    E2E_CHOICES, FOCUS_CHOICES, STAGE_CHOICES, TRACK_CHOICES,
)
from aether.challenger_runtime.judge_client import JudgeClient
from aether.execution import MemoryExecutor
from aether.ledger import ExecutionLedger, Receipt
from aether.progress_checkpoints import (
    ProgressCheckpointsError, build_progress_checkpoints_launch_binding,
    progress_checkpoints_runtime_identity,
)


TASK = "Describe a careful implementation.\n" + ("Keep the user-visible behavior stable.\n" * 180)


def test_state_snapshot_selector_defaults_off_and_v2_requires_it():
    control = build_progress_checkpoints_launch_binding(
        "control", claim_ledger="challenger_v5", deadline_visibility="visible_v1")
    assert control["state_snapshot"] == "control"
    assert "state_snapshot" not in control["manifest"]
    assert "AETHER_G4_STATE_SNAPSHOT" not in control["env"]
    host_g1 = build_progress_checkpoints_launch_binding(
        "control", claim_ledger="control", deadline_visibility="control", state_snapshot="v1")
    assert host_g1["manifest"]["state_snapshot"] == "v1"
    assert host_g1["env"]["AETHER_G4_STATE_SNAPSHOT"] == "v1"
    g1 = build_progress_checkpoints_launch_binding(
        "control", claim_ledger="challenger_v5", deadline_visibility="visible_v1", state_snapshot="v1")
    assert g1["manifest"]["state_snapshot"] == "v1"
    assert g1["env"]["AETHER_G4_STATE_SNAPSHOT"] == "v1"
    with pytest.raises(ProgressCheckpointsError, match="requires --state-snapshot v1"):
        build_progress_checkpoints_launch_binding(
            "control", claim_ledger="challenger_v5", deadline_visibility="visible_v1", mode="v2")
    v2 = build_progress_checkpoints_launch_binding(
        "control", claim_ledger="challenger_v5", deadline_visibility="visible_v1",
        mode="v2", state_snapshot="v1")
    assert v2["progress_checkpoints"] == "25,50,75,85"
    with pytest.raises(ProgressCheckpointsError, match="requires --progress-checkpoints-mode v2"):
        build_progress_checkpoints_launch_binding(
            "control", claim_ledger="challenger_v5", deadline_visibility="visible_v1",
            state_snapshot="v1", success_contract="v1")
    contract = build_progress_checkpoints_launch_binding(
        "control", claim_ledger="challenger_v5", deadline_visibility="visible_v1",
        mode="v2", state_snapshot="v1", success_contract="v1")
    assert contract["env"]["AETHER_G4_SUCCESS_CONTRACT"] == "v1"
    assert "state_snapshot" not in progress_checkpoints_runtime_identity("control", "control")
    assert progress_checkpoints_runtime_identity("control", "control", "v1")["state_snapshot"] == "v1"


def _typed_answers(request):
    choices = {
        "stage": STAGE_CHOICES[1],
        "end_to_end_run_exists": "no",
        "on_track_for_remaining_time": TRACK_CHOICES[1],
        "biggest_gap": "none",
        "recommended_focus": FOCUS_CHOICES[-1],
    }
    return {"answers": {
        key: {"choice": choices[key.removeprefix("progress_checkpoint:")], "confidence": 0.8}
        for key in request["questions"]
    }}


@pytest.mark.parametrize("mode", ["challenger_v5", "challenger_v4"])
def test_crossed_checkpoints_report_real_failures_and_latest_command_outputs(tmp_path, mode):
    requests = []

    def progress_transport(request):
        requests.append(request)
        return _typed_answers(request)

    evaluator = JudgeClient(
        lambda _request: {}, model="offline-fake", raw_task=TASK,
        progress_transport=progress_transport,
    )
    controller = ChallengerController(
        card_model=lambda _messages: "", evaluator=evaluator,
        evidence_dir=tmp_path, run_id="checkpoint-run", task_text=TASK,
        mode=mode, progress_fractions=(25, 50),
    )
    executor = MemoryExecutor(workspace_root="/app", files={"main.py": "current edit"})
    ledger = ExecutionLedger()
    ledger.record(Receipt("read-failed", 2, "read_file", False, "missing"))
    ledger.record(Receipt("edit", 3, "edit_file", True, "edited", payload={"path": "main.py"}))
    ledger.record(Receipt("run-failed", 4, "run_command", False, "exit 1", payload={
        "command": "python -m compileall .", "exit_code": 1,
        "stdout": "compilation started", "stderr": "SyntaxError: invalid syntax",
    }))
    ledger.record(Receipt("run-ok", 5, "run_command", True, "exit 0", payload={
        "command": "python app.py", "exit_code": 0, "stdout": "application started",
    }))
    controller.bind(kernel=None, compiled=None, executor=executor, exec_ledger=ledger, world_state=None)

    # A delayed turn boundary catches both crossed fractions; neither repeats later.
    controller.on_turn_boundary(step=6, elapsed_sec=51, deadline_sec=100)
    controller.on_turn_boundary(step=7, elapsed_sec=80, deadline_sec=100)

    assert len(requests) == 2
    assert [r["state"]["claim_card"]["checkpoint_fraction_percent"] for r in requests] == [25, 50]
    for request in requests:
        assert request["state"]["raw_task"] == TASK
        card = request["state"]["claim_card"]
        assert card["action_summary"]["explore_actions"] == 1
        assert card["action_summary"]["edit_actions"] == 1
        assert card["action_summary"]["run_actions"] == 2
        assert card["action_summary"]["first_end_to_end_run_step"] is None
        assert card["action_summary"]["first_end_to_end_run_step_status"] == "unknown_not_inferred"
        assert request["state"]["visible_evidence"]
        visible = "\n".join(request["state"]["visible_evidence"].values())
        assert "SyntaxError: invalid syntax" in visible
        assert "application started" in visible
        assert "current edit" in visible

    feedback = controller.pop_feedback()["text"]
    assert "Progress check at 25% of time" in feedback
    assert "end-to-end run: no" in feedback
    # Notes inform, never direct: the focus answer is logged but not shown to the solver.
    assert "focus" not in feedback.lower()
    events = [json.loads(line) for line in (tmp_path / "challenger_events.jsonl").read_text().splitlines()]
    checkpoints = [event for event in events if event["event"] == "progress_checkpoint"]
    assert [event["fraction_percent"] for event in checkpoints] == [25, 50]
    assert all(event["request_bytes"] <= 120_000 for event in checkpoints)


def test_empty_state_uses_evidence_free_questions_without_fabricated_stage(tmp_path):
    requests = []

    def progress_transport(request):
        requests.append(request)
        return _typed_answers(request)

    controller = ChallengerController(
        card_model=lambda _messages: "",
        evaluator=JudgeClient(lambda _request: {}, model="offline-fake", raw_task="", progress_transport=progress_transport),
        evidence_dir=tmp_path, run_id="empty", task_text="Make a change.",
        mode="challenger_v5", progress_fractions=(50,),
    )
    controller.bind(kernel=None, compiled=None, executor=MemoryExecutor(workspace_root="/app"),
                    exec_ledger=ExecutionLedger(), world_state=None)
    controller.on_turn_boundary(step=1, elapsed_sec=50, deadline_sec=100)

    request = requests[0]
    assert request["state"]["visible_evidence"] == {}
    assert all(not question.get("evidence_refs") for question in request["questions"].values())
    assert request["questions"]["progress_checkpoint:stage"]["criteria"] == {
        choice: choice for choice in STAGE_CHOICES
    }


def test_failed_checkpoint_callback_is_logged_and_does_not_block_later_fraction(tmp_path):
    attempts = []

    def progress_transport(request):
        fraction = request["state"]["claim_card"]["checkpoint_fraction_percent"]
        attempts.append(fraction)
        if fraction == 25:
            raise RuntimeError("offline fake transport failure")
        return _typed_answers(request)

    controller = ChallengerController(
        card_model=lambda _messages: "",
        evaluator=JudgeClient(lambda _request: {}, model="offline-fake", raw_task="",
                               progress_transport=progress_transport),
        evidence_dir=tmp_path, run_id="callback-error", task_text="Make a change.",
        mode="challenger_v5", progress_fractions=(25, 50),
    )
    controller.bind(kernel=None, compiled=None, executor=MemoryExecutor(workspace_root="/app"),
                    exec_ledger=ExecutionLedger(), world_state=None)
    controller.on_turn_boundary(step=1, elapsed_sec=25, deadline_sec=100)
    assert controller.pop_feedback() is None
    controller.on_turn_boundary(step=2, elapsed_sec=50, deadline_sec=100)

    assert attempts == [25, 50]
    assert "Progress check at 50%" in controller.pop_feedback()["text"]
    events = [json.loads(line) for line in (tmp_path / "challenger_events.jsonl").read_text().splitlines()]
    errors = [event for event in events if event["event"] == "progress_checkpoint_error"]
    assert len(errors) == 1 and errors[0]["fraction_percent"] == 25
    assert [event["fraction_percent"] for event in events if event["event"] == "progress_checkpoint"] == [50]


def test_boolean_confidence_is_invalid_and_callback_remains_advisory(tmp_path):
    requests = []

    def progress_transport(request):
        requests.append(request)
        answers = _typed_answers(request)["answers"]
        first = next(iter(answers))
        answers[first]["confidence"] = True
        return {"answers": answers}

    controller = ChallengerController(
        card_model=lambda _messages: "",
        evaluator=JudgeClient(lambda _request: {}, model="offline-fake", raw_task="",
                               progress_transport=progress_transport),
        evidence_dir=tmp_path, run_id="boolean-confidence", task_text="Make a change.",
        mode="challenger_v5", progress_fractions=(50,),
    )
    controller.bind(kernel=None, compiled=None, executor=MemoryExecutor(workspace_root="/app"),
                    exec_ledger=ExecutionLedger(), world_state=None)

    controller.on_turn_boundary(step=1, elapsed_sec=50, deadline_sec=100)

    assert len(requests) == 1
    assert controller.pop_feedback() is None
    events = [json.loads(line) for line in (tmp_path / "challenger_events.jsonl").read_text().splitlines()]
    errors = [event for event in events if event["event"] == "progress_checkpoint_error"]
    assert len(errors) == 1 and "invalid confidence" in errors[0]["error"]


def test_shell_multi_file_refs_do_not_hide_a_later_edit_file(tmp_path):
    requests = []
    evaluator = JudgeClient(
        lambda _request: {}, model="offline-fake", raw_task="Make the requested changes.",
        progress_transport=lambda request: requests.append(request) or _typed_answers(request),
    )
    controller = ChallengerController(
        card_model=lambda _messages: "", evaluator=evaluator, evidence_dir=tmp_path,
        run_id="unique-file-refs", task_text="Make the requested changes.",
        mode="challenger_v5", progress_fractions=(50,),
    )
    executor = MemoryExecutor(workspace_root="/app", files={
        "a.py": "alpha", "b.py": "bravo", "c.py": "charlie",
    })
    ledger = ExecutionLedger()
    ledger.record(Receipt("shell-write", 3, "run_command", True, "wrote two files", payload={
        "command": "python generate.py", "exit_code": 0, "modified_paths": ["a.py", "b.py"],
    }))
    ledger.record(Receipt("later-edit", 4, "edit_file", True, "edited c", payload={"path": "c.py"}))
    controller.bind(kernel=None, compiled=None, executor=executor, exec_ledger=ledger, world_state=None)

    controller.on_turn_boundary(step=5, elapsed_sec=50, deadline_sec=100)

    request = requests[0]
    views = request["state"]["visible_evidence"]
    file_views = [text for text in views.values() if text.startswith("[file ")]
    assert len(file_views) == 3
    assert all(content in "\n".join(file_views) for content in ("alpha", "bravo", "charlie"))
    assert len(request["state"]["claim_card"]["evidence_refs"]) == len(set(
        request["state"]["claim_card"]["evidence_refs"]
    ))
    c_view = next(text for text in views.values() if "charlie" in text)
    assert "[file c.py]" in c_view and "t4" in c_view and "current_after_edit" in c_view
    assert request["state"]["claim_card"]["evidence_omitted_refs"] == []


def test_progress_checkpoints_reject_modes_without_completion_review():
    with pytest.raises(ProgressCheckpointsError, match="challenger_v4 or challenger_v5"):
        build_progress_checkpoints_launch_binding(
            "25,50", claim_ledger="challenger_v2", deadline_visibility="visible_v1")


@pytest.mark.parametrize("ledger,ok", [("challenger_v4", True), ("challenger_v5", True), ("challenger_v2", False)])
def test_agent_launch_guard_accepts_challenger_v4_and_v5(monkeypatch, ledger, ok):
    from aether import research_glm_harbor_agent as agent
    monkeypatch.setenv(agent.PROGRESS_CHECKPOINTS_ENV, "25,50,75,90")
    if ok:
        assert agent.g4_progress_checkpoints(ledger, agent.DEADLINE_VISIBLE_V1)[1] == (25, 50, 75, 90)
    else:
        with pytest.raises(RuntimeError, match="challenger_v4 or challenger_v5"):
            agent.g4_progress_checkpoints(ledger, agent.DEADLINE_VISIBLE_V1)
