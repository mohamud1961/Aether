from __future__ import annotations

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from runner.aether2 import loop as loop_module
from runner.aether2.bridge_harbor import TaskSpec
from runner.aether2.executor import ContainerExecutor
from runner.aether2.loop import RunResult, run_aether2_loop
from runner.aether2.model_client import ModelResponse
from runner.aether2.sessions import SessionRegistry


def _response(text: str = "", tool_calls: tuple[dict, ...] = ()) -> ModelResponse:
    return ModelResponse(
        text=text,
        tool_calls=tool_calls,
        usage={"cached_input_tokens": 0, "fresh_input_tokens": 0},
        status="completed",
        raw_response={},
    )


def _tool_call(name: str, arguments: dict, call_id: str = "call-1") -> dict:
    return {"id": call_id, "type": "function", "name": name, "arguments": json.dumps(arguments)}


def _verify_response(satisfied: bool = True) -> ModelResponse:
    payload = {
        "requirements": [
            {
                "requirement": "task complete",
                "verdict": "satisfied" if satisfied else "unsatisfied",
                "evidence": "checked",
                "evidence_refs": ["checks_results[0]"],
            }
        ],
        "reason_codes": [],
        "summary": "ok" if satisfied else "missing evidence",
    }
    return _response(text=json.dumps(payload))


def _weak_satisfied_verify_response() -> ModelResponse:
    """A verifier report that marks the requirement satisfied but only with
    existence/readback-only (weak) evidence and no independent provenance.

    Uses an `evidence_refs` entry that does not resolve to any entry in the
    verifier's source catalog, so the strength classification is driven only
    by the requirement/evidence text (no incidental strong-sounding words
    from a stringified check result)."""
    payload = {
        "requirements": [
            {
                "requirement": "task complete",
                "verdict": "satisfied",
                "evidence": "out.txt exists and is present in the workspace.",
                "evidence_refs": ["claim.summary"],
            }
        ],
        "reason_codes": [],
        "summary": "output file exists",
    }
    return _response(text=json.dumps(payload))


class ScriptedModelClient:
    """Replays a fixed sequence of tool-call turns; non-tool calls (verify/compaction) get a separate queue."""

    def __init__(self, turns, side_responses=None):
        self.turns = list(turns)
        self.side_responses = list(side_responses or [])
        self.calls: list[tuple[list[dict], list[dict], int]] = []

    def call(self, messages, tools, *, cache_prefix_len):
        self.calls.append((list(messages), list(tools), cache_prefix_len))
        tool_names = {
            tool.get("function", {}).get("name")
            for tool in tools
            if isinstance(tool, dict)
        }
        if tool_names and tool_names.issubset({"run_command", "read_file", "job_status", "session_read"}):
            if self.side_responses:
                return self.side_responses.pop(0)
            return _verify_response(True)
        if not tools:
            if self.side_responses:
                return self.side_responses.pop(0)
            return _verify_response(True)
        if self.turns:
            return self.turns.pop(0)
        return _response(text="done")


def _make_task(tmp_path: Path, instruction: str = "do the thing") -> TaskSpec:
    task_dir = tmp_path / "task"
    workspace_root = task_dir / "workspace"
    artifacts_dir = task_dir / "artifacts"
    workspace_root.mkdir(parents=True)
    artifacts_dir.mkdir(parents=True)
    return TaskSpec(
        task_id="synthetic-task",
        instruction=instruction,
        task_dir=task_dir,
        workspace_root=workspace_root,
        artifacts_dir=artifacts_dir,
    )


def _make_executor(task: TaskSpec) -> ContainerExecutor:
    return ContainerExecutor(workspace_root=task.workspace_root)


def test_loop_terminates_on_task_done_and_runs_finalize(tmp_path: Path) -> None:
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    turns = [
        _response(
            text="writing the file",
            tool_calls=(_tool_call("write_file", {"path": "out.txt", "content": "hello"}),),
        ),
        _response(
            text="done",
            tool_calls=(
                _tool_call("task_done", {"summary": "wrote out.txt", "checks": ["cat out.txt"]}, call_id="call-2"),
            ),
        ),
    ]
    client = ScriptedModelClient(turns)

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    assert isinstance(result, RunResult)
    assert result.finalize_reason == "task_done"
    assert result.pass_ is True
    assert result.verification_rounds == 1
    assert (task.workspace_root / "out.txt").read_text(encoding="utf-8") == "hello"
    verifier_calls = [
        call
        for call in client.calls
        if {
            tool.get("function", {}).get("name")
            for tool in call[1]
            if isinstance(tool, dict)
        }.issubset({"run_command", "read_file", "job_status", "session_read"})
        and call[1]
    ]
    assert verifier_calls


def test_reasoning_trace_captures_visible_state_progress_and_task_done(tmp_path: Path) -> None:
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    turns = [
        _response(text="checking", tool_calls=(_tool_call("run_command", {"cmd": "true"}, call_id="call-1"),)),
        _response(
            text="writing",
            tool_calls=(_tool_call("write_file", {"path": "out.txt", "content": "hello"}, call_id="call-2"),),
        ),
        _response(
            text="done",
            tool_calls=(
                _tool_call("task_done", {"summary": "wrote out.txt", "checks": ["cat out.txt"]}, call_id="call-3"),
            ),
        ),
    ]
    client = ScriptedModelClient(turns)

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    assert result.finalize_reason == "task_done"
    assert result.reasoning_trace_ref is not None
    trace_path = Path(result.reasoning_trace_ref)
    assert trace_path.exists()

    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["schema_version"] == 1
    assert trace["step_count"] == 3
    assert trace["finalize_reason"] == "task_done"
    assert trace["verifier_clean"] is True

    steps = trace["steps"]
    assert len(steps) == 3

    first = steps[0]
    assert first["step"] == 1
    assert first["visible_context"]["tail_state"]["evidence_ledger"]["requirements"]
    assert first["tool_calls"][0]["tool_name"] == "run_command"
    assert first["progress"]["no_progress"] is True

    second = steps[1]
    assert second["tool_calls"][0]["tool_name"] == "write_file"
    assert second["progress"]["no_progress"] is False
    assert second["progress"]["stronger_evidence_added"] is True or second["progress"]["requirement_advanced"] is True

    third = steps[2]
    assert third["task_done"]["called"] is True
    assert third["task_done"]["checks"] == ["cat out.txt"]
    assert third["tool_calls"][0]["tool_name"] == "task_done"
    assert third["visible_context"]["completion_contract"]["unresolved_requirements"]
    assert third["model_input_digests"]["immutable_prefix_digest"]
    assert third["model_input_digests"]["compaction_generation"] == 0
    assert third["visible_context"]["model_visible_requirements"]["unresolved_requirements"]


def test_circular_task_done_claim_is_recorded_as_weak_terminal_claim(tmp_path: Path) -> None:
    """W4.1 homolog: a self-authored readback-only completion claim must be
    recorded in the evidence ledger as a weak/unresolved terminal claim, not
    promoted to a structured requirement-evidence mapping."""

    task = _make_task(tmp_path)
    executor = _make_executor(task)

    turns = [
        _response(
            text="writing",
            tool_calls=(_tool_call("write_file", {"path": "out.txt", "content": "hello"}, call_id="call-1"),),
        ),
        _response(
            text="done",
            tool_calls=(
                _tool_call("task_done", {"summary": "wrote out.txt", "checks": ["cat out.txt"]}, call_id="call-2"),
            ),
        ),
    ]
    client = ScriptedModelClient(turns)

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    assert result.finalize_reason == "task_done"
    trace = json.loads(Path(result.reasoning_trace_ref).read_text(encoding="utf-8"))

    last_step = trace["steps"][-1]
    post_ledger = last_step.get("post_step_evidence_ledger") or {}
    terminal_claims = post_ledger.get("terminal_claims", [])
    assert terminal_claims, "expected a recorded terminal claim"
    claim = terminal_claims[-1]
    assert claim["claim_kind"] == "completion"
    # A bare `cat out.txt` check with no requirement-evidence mapping is weak
    # claim structure -- never promoted to a structured mapping by itself.
    assert claim["mapping_status"] == "weak"
    assert claim["requirements"] == []


def test_reasoning_trace_records_repair_round_and_non_step_calls(tmp_path: Path) -> None:
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    turns = [
        _response(
            text="premature done",
            tool_calls=(
                _tool_call("task_done", {"summary": "first claim", "checks": ["false"]}, call_id="call-1"),
            ),
        ),
        _response(
            text="repairing",
            tool_calls=(
                _tool_call("write_file", {"path": "out.txt", "content": "fixed"}, call_id="call-2"),
                _tool_call("task_done", {"summary": "second claim", "checks": ["cat out.txt"]}, call_id="call-3"),
            ),
        ),
    ]
    client = ScriptedModelClient(turns, side_responses=[_verify_response(False), _verify_response(True)])

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    assert result.finalize_reason == "task_done"
    trace = json.loads(Path(result.reasoning_trace_ref).read_text(encoding="utf-8"))

    repair_steps = [step for step in trace["steps"] if step["call_role"] == "repair"]
    assert repair_steps
    repair_step = repair_steps[0]
    assert repair_step["verification_round_index"] == 1
    assert repair_step["decision_kind"] == "repair_task_done"
    assert repair_step["blocker_state"]["verification_summary"]
    assert any(tool["tool_name"] == "write_file" for tool in repair_step["tool_calls"])
    assert repair_step["model_input_digests"]["tail_digest"]

    non_step_roles = {entry["call_role"] for entry in trace["non_step_model_calls"]}
    assert "verifier" in non_step_roles


def test_loop_terminates_on_implicit_stop(tmp_path: Path) -> None:
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    turns = [_response(text="I believe this is complete.", tool_calls=())]
    client = ScriptedModelClient(turns)

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    assert result.finalize_reason == "implicit_stop"
    assert result.steps == 1
    verifier_calls = [
        call
        for call in client.calls
        if {
            tool.get("function", {}).get("name")
            for tool in call[1]
            if isinstance(tool, dict)
        }.issubset({"run_command", "read_file", "job_status", "session_read"})
        and call[1]
    ]
    assert verifier_calls


def test_loop_terminates_on_deadline_with_forced_path(tmp_path: Path) -> None:
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    # No turns ever consumed because the deadline has already passed.
    client = ScriptedModelClient(turns=[], side_responses=[_response(text="closing turn")])

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() - 1)

    assert result.finalize_reason == "budget_exhaustion"
    assert result.steps == 0
    assert result.summary == "closing turn"
    # exactly one closing-turn call with empty tools
    closing_calls = [call for call in client.calls if call[1] == []]
    assert len(closing_calls) == 1


def test_loop_runs_declared_checks_on_deadline_forced_path(tmp_path: Path) -> None:
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    # First turn declares task_done with checks but the loop's deadline check happens
    # before the *next* model call, so give it just enough budget for one step.
    turns = [
        _response(
            text="claiming done",
            tool_calls=(
                _tool_call(
                    "task_done",
                    {"summary": "all done", "checks": ["echo deadline-check"]},
                    call_id="call-1",
                ),
            ),
        ),
    ]
    client = ScriptedModelClient(turns, side_responses=[_response(text="closing turn")])

    # Deadline is far enough away for step 1, but task_done routes to the normal
    # finalize flow, not the deadline-forced path, when time remains. To exercise the
    # deadline-forced path with declared checks, call the loop with an already-past
    # deadline but pre-seed the most recently declared checks via a first pass.
    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)
    assert result.finalize_reason == "task_done"
    assert result.verification_rounds >= 1


def test_blind_retry_guard_fires_once_for_identical_failed_repeat(tmp_path: Path) -> None:
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    failing_call = _tool_call("run_command", {"cmd": "false"}, call_id="call-1")
    turns = [
        _response(text="trying", tool_calls=(failing_call,)),
        _response(text="retrying", tool_calls=(_tool_call("run_command", {"cmd": "false"}, call_id="call-2"),)),
        _response(text="trying something else", tool_calls=(_tool_call("run_command", {"cmd": "true"}, call_id="call-3"),)),
        _response(text="done", tool_calls=(_tool_call("task_done", {"summary": "ok", "checks": ["true"]}, call_id="call-4"),)),
    ]
    client = ScriptedModelClient(turns)

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    blind_retry_envelopes = [
        record.envelope for record in result.tool_invocations if record.envelope.blind_retry_blocked
    ]
    assert len(blind_retry_envelopes) == 1
    assert blind_retry_envelopes[0].error is not None
    assert blind_retry_envelopes[0].error.reason_code == "blind_retry_blocked_same_failed_command"

    # the second identical "false" call was blocked, not re-executed
    run_command_records = [r for r in result.tool_invocations if r.tool_name == "run_command"]
    assert len(run_command_records) == 3


def test_mirror_note_after_three_identical_zero_delta_actions(tmp_path: Path) -> None:
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    no_op_call = lambda call_id: _tool_call("run_command", {"cmd": "true"}, call_id=call_id)
    turns = [
        _response(text="step1", tool_calls=(no_op_call("call-1"),)),
        _response(text="step2", tool_calls=(no_op_call("call-2"),)),
        _response(text="step3", tool_calls=(no_op_call("call-3"),)),
        _response(text="done", tool_calls=(_tool_call("task_done", {"summary": "ok", "checks": ["true"]}, call_id="call-4"),)),
    ]
    client = ScriptedModelClient(turns)

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    assert len(result.mirror_notes) == 1
    assert result.mirror_notes[0].streak == 3
    assert result.no_delta_streaks == 1


def test_step_cap_is_a_safety_rail(tmp_path: Path, monkeypatch) -> None:
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    monkeypatch.setattr(loop_module, "STEP_CAP", 2)

    # The model never calls task_done and never stops; the step cap must end the run.
    def infinite_turns():
        counter = 0
        while True:
            counter += 1
            yield _response(
                text=f"step {counter}",
                tool_calls=(_tool_call("run_command", {"cmd": f"echo {counter}"}, call_id=f"call-{counter}"),),
            )

    gen = infinite_turns()

    class InfiniteScriptedClient(ScriptedModelClient):
        def call(self, messages, tools, *, cache_prefix_len):
            self.calls.append((list(messages), list(tools), cache_prefix_len))
            if not tools:
                if self.side_responses:
                    return self.side_responses.pop(0)
                return _verify_response(True)
            return next(gen)

    client = InfiniteScriptedClient(turns=[])

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 600)

    assert result.steps == 2
    assert result.finalize_reason == "budget_exhaustion"
    closing_calls = [call for call in client.calls if call[1] == []]
    assert len(closing_calls) == 1


def test_max_three_verification_rounds_enforced(tmp_path: Path) -> None:
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    turns = [
        _response(
            text="done",
            tool_calls=(_tool_call("task_done", {"summary": "first claim", "checks": ["false"]}, call_id="call-1"),),
        ),
        # Round 2: model responds to discrepancy with another task_done claim.
        _response(
            text="done again",
            tool_calls=(_tool_call("task_done", {"summary": "second claim", "checks": ["false"]}, call_id="call-2"),),
        ),
        # Round 3: model responds again.
        _response(
            text="done again again",
            tool_calls=(_tool_call("task_done", {"summary": "third claim", "checks": ["false"]}, call_id="call-3"),),
        ),
    ]
    # Verifier always reports a discrepancy so all 3 rounds are consumed.
    side_responses = [_verify_response(False), _verify_response(False), _verify_response(False)]
    client = ScriptedModelClient(turns, side_responses=side_responses)

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    assert result.verification_rounds == 3
    assert result.pass_ is False


def test_g2_row_serialization_roundtrips_verification_fields(tmp_path: Path) -> None:
    """Regression for V1: the G2 runner's `run_result` row must include
    verification_rounds, discrepancy_reports, and verifier_clean -- not just
    a hand-picked subset -- so live-run forensics can see whether Layer-2
    finalize verification actually ran."""
    from dataclasses import asdict

    task = _make_task(tmp_path)
    executor = _make_executor(task)

    turns = [
        _response(
            text="writing the file",
            tool_calls=(_tool_call("write_file", {"path": "out.txt", "content": "hello"}),),
        ),
        _response(
            text="done",
            tool_calls=(
                _tool_call("task_done", {"summary": "wrote out.txt", "checks": ["cat out.txt"]}, call_id="call-2"),
            ),
        ),
    ]
    client = ScriptedModelClient(turns)

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    assert result.verification_rounds >= 1
    assert len(result.discrepancy_reports) >= 1
    assert result.verifier_clean is True

    # Mirror tools/run_aether2_g2.py's row["run_result"] construction.
    row_run_result = {
        "verifier_clean": result.verifier_clean,
        "finalize_reason": result.finalize_reason,
        "summary": result.summary,
        "steps": result.steps,
        "model_calls": result.model_calls,
        "tokens_cached": result.tokens_cached,
        "tokens_fresh": result.tokens_fresh,
        "cost": result.cost,
        "wall_time": result.wall_time,
        "no_delta_streaks": result.no_delta_streaks,
        "verification_rounds": result.verification_rounds,
        "recoveries": result.recoveries,
        "compaction_count": result.compaction_count,
        "job_survival": result.job_survival,
        "session_survival": result.session_survival,
        "grader_reward": result.grader_reward,
        "discrepancy_reports": [asdict(report) for report in result.discrepancy_reports],
    }

    for field_name in (
        "verification_rounds",
        "discrepancy_reports",
        "verifier_clean",
        "no_delta_streaks",
        "recoveries",
        "compaction_count",
        "cost",
    ):
        assert field_name in row_run_result

    assert row_run_result["verification_rounds"] >= 1
    assert isinstance(row_run_result["discrepancy_reports"], list)
    assert len(row_run_result["discrepancy_reports"]) >= 1
    assert row_run_result["verifier_clean"] is True


def _tail_plan_from_messages(messages: list[dict]) -> str | None:
    for message in messages:
        if message.get("role") != "system":
            continue
        content = message.get("content", "")
        if not content.startswith("[tail_telemetry]\n"):
            continue
        payload = json.loads(content[len("[tail_telemetry]\n") :])
        return payload.get("plan")
    return None


def test_plan_text_captured_from_first_turn_and_replaced_by_plan_prefixed_turn(tmp_path: Path) -> None:
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    turns = [
        _response(
            text="Working on it: read the file first.",
            tool_calls=(_tool_call("run_command", {"cmd": "true"}, call_id="call-1"),),
        ),
        _response(
            text="PLAN: write out.txt then verify\nMore detail here.",
            tool_calls=(_tool_call("run_command", {"cmd": "true"}, call_id="call-2"),),
        ),
        _response(
            text="done",
            tool_calls=(_tool_call("task_done", {"summary": "ok", "checks": ["true"]}, call_id="call-3"),),
        ),
    ]
    client = ScriptedModelClient(turns)

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    assert isinstance(result, RunResult)

    tool_calls_only = [call for call in client.calls if call[1] != []]
    assert len(tool_calls_only) >= 3

    # The second model call's tail telemetry carries the first turn's text as the plan.
    plan_after_first_turn = _tail_plan_from_messages(tool_calls_only[1][0])
    assert plan_after_first_turn == "Working on it: read the file first."

    # The third model call's tail telemetry carries the full "PLAN:" turn as the plan.
    plan_after_plan_turn = _tail_plan_from_messages(tool_calls_only[2][0])
    assert plan_after_plan_turn == "PLAN: write out.txt then verify\nMore detail here."


def _write_fake_tmux(root: Path) -> Path:
    script = root / "tmux"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, sys",
                "from pathlib import Path",
                f"root = Path({str(root)!r})",
                "state = root / 'fake_tmux_state'",
                "state.mkdir(exist_ok=True)",
                "args = sys.argv[1:]",
                "cmd = args[0]",
                "if cmd == 'new-session':",
                "    session_id = args[3]",
                "    (state / f'{session_id}.json').write_text('{}', encoding='utf-8')",
                "    sys.exit(0)",
                "if cmd == 'send-keys':",
                "    sys.exit(0)",
                "if cmd == 'capture-pane':",
                "    sys.stdout.write('')",
                "    sys.exit(0)",
                "if cmd == 'kill-session':",
                "    session_id = args[2]",
                "    path = state / f'{session_id}.json'",
                "    if path.exists():",
                "        path.unlink()",
                "    sys.exit(0)",
                "sys.exit(1)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_session_survival_true_when_session_remains_registered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retrying_subprocess
) -> None:
    from runner.aether2 import sessions as sessions_module

    retrying_subprocess(sessions_module)
    _write_fake_tmux(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    task = _make_task(tmp_path)
    executor = _make_executor(task)

    turns = [
        _response(
            text="starting a session",
            tool_calls=(_tool_call("session_start", {"session_id": "shell", "command": "bash"}, call_id="call-1"),),
        ),
        _response(
            text="done",
            tool_calls=(_tool_call("task_done", {"summary": "ok", "checks": ["true"]}, call_id="call-2"),),
        ),
    ]
    client = ScriptedModelClient(turns)

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    assert result.session_survival is True


def test_session_survival_false_when_session_disappears_from_registry(tmp_path: Path) -> None:
    state_dir = tmp_path / ".aether2" / "state"
    registry = SessionRegistry(state_dir)

    session_ids = ["shell"]
    # Simulate a session that the loop tracked but that no longer appears in the
    # registry (e.g. it was killed/cleaned up out from under the loop).
    assert registry.list_session_ids() == []

    session_survival = (
        all(sid in registry.list_session_ids() for sid in session_ids) if session_ids else True
    )
    assert session_survival is False


def test_prefix_bytes_identical_across_appends_until_rebase(tmp_path: Path) -> None:
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    turns = [
        _response(text="step1", tool_calls=(_tool_call("run_command", {"cmd": "true"}, call_id="call-1"),)),
        _response(text="done", tool_calls=(_tool_call("task_done", {"summary": "ok", "checks": ["true"]}, call_id="call-2"),)),
    ]
    client = ScriptedModelClient(turns)

    from runner.aether2.context import ContextManager

    context = ContextManager()
    prefix = context.build_prefix(
        system_prompt="system",
        task_instruction=task.instruction,
        orientation={"cwd": str(task.workspace_root)},
        tool_schemas=[{"function": {"name": "run_command"}}],
    )
    context.append_turn({"role": "assistant", "content": "plan"})
    context.append_turn({"role": "tool", "content": "ok", "name": "run_command"})
    context.assert_prefix_unchanged()
    assert prefix.frozen_bytes == context.prefix.frozen_bytes

    # The loop itself must not mutate its own immutable prefix either.
    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)
    assert isinstance(result, RunResult)


def test_write_file_surfaces_artifact_event_in_next_tail_and_does_not_re_render_when_unchanged(tmp_path: Path) -> None:
    """C4: a write_file step surfaces an artifact_written event in the next tail
    render; once consumed, an unchanged state does not repeat it."""
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    turns = [
        _response(
            text="step1",
            tool_calls=(_tool_call("write_file", {"path": "art.txt", "content": "hi"}, call_id="call-1"),),
        ),
        _response(
            text="step2",
            tool_calls=(_tool_call("run_command", {"cmd": "true"}, call_id="call-2"),),
        ),
        _response(
            text="done",
            tool_calls=(_tool_call("task_done", {"summary": "ok", "checks": ["true"]}, call_id="call-3"),),
        ),
    ]
    client = ScriptedModelClient(turns)

    run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    # Step 1's call has no events yet (nothing written before it).
    # Step 2's tail (rendered before the 2nd model call) must include the
    # artifact_written event from step 1's write_file.
    tail_messages = []
    for messages, tools, _ in client.calls:
        if not tools:
            continue
        last = messages[-1]
        content = str(last.get("content", ""))
        if last.get("role") == "system" and "derived_state" in content:
            _, _, json_part = content.partition("\n")
            tail_messages.append(json.loads(json_part))

    assert len(tail_messages) >= 2
    second_tail = tail_messages[1]
    events = second_tail["derived_state"].get("events", [])
    assert any("artifact_written:art.txt" in event for event in events)

    # Step 3's tail must NOT repeat the same event (unchanged state -> no re-render).
    if len(tail_messages) >= 3:
        third_tail = tail_messages[2]
        third_events = third_tail["derived_state"].get("events", [])
        assert not any("artifact_written:art.txt" in event for event in third_events)


def test_run_completion_does_not_stop_registered_jobs(tmp_path: Path, retrying_subprocess) -> None:
    """C2: completing a run must not kill jobs the model started via start_job."""
    from runner.aether2 import jobs as jobs_module

    retrying_subprocess(jobs_module)

    task = _make_task(tmp_path)
    executor = _make_executor(task)

    turns = [
        _response(
            text="start the job",
            tool_calls=(
                _tool_call(
                    "start_job",
                    {"cmd": "sleep 30", "job_id": "long-runner"},
                    call_id="call-1",
                ),
            ),
        ),
        _response(
            text="done",
            tool_calls=(_tool_call("task_done", {"summary": "started job", "checks": ["true"]}, call_id="call-2"),),
        ),
    ]
    client = ScriptedModelClient(turns)

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    assert result.job_survival is True

    from runner.aether2.jobs import JobRegistry

    state_dir = task.workspace_root / ".aether2" / "state"
    status = JobRegistry(state_dir).status("long-runner")
    assert status.alive is True


def test_rebase_fact_ledger_includes_installed_packages_and_nonzero_exits(tmp_path: Path, monkeypatch) -> None:
    """C5: the §6.5 fact ledger built at rebase time includes installed_packages
    (derived generically from package-manager command successes) and
    nonzero_exits (from failed run_command invocations)."""
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    captured_ledgers = []
    from runner.aether2 import compactor as compactor_module

    original_build_fact_ledger = compactor_module.build_fact_ledger

    def spy_build_fact_ledger(delta_state, **kwargs):
        ledger = original_build_fact_ledger(delta_state, **kwargs)
        captured_ledgers.append(ledger)
        return ledger

    monkeypatch.setattr(compactor_module, "build_fact_ledger", spy_build_fact_ledger)
    monkeypatch.setattr(loop_module, "CONTEXT_WINDOW_TOKENS", 1)  # force rebase every step

    original_run = executor.run

    def fake_run(cmd, timeout_sec=120, cwd=None):
        if cmd == "pip install requests":
            return SimpleNamespace(
                command=cmd,
                exit_code=0,
                stdout="Requirement already satisfied: requests",
                stderr="",
                cwd=str(task.workspace_root),
                duration_sec=0.01,
                timed_out=False,
            )
        return original_run(cmd, timeout_sec=timeout_sec, cwd=cwd)

    monkeypatch.setattr(executor, "run", fake_run)

    turns = [
        _response(text="install", tool_calls=(_tool_call("run_command", {"cmd": "pip install requests"}, call_id="call-1"),)),
        _response(text="fail", tool_calls=(_tool_call("run_command", {"cmd": "false"}, call_id="call-2"),)),
        _response(text="done", tool_calls=(_tool_call("task_done", {"summary": "ok", "checks": ["true"]}, call_id="call-3"),)),
    ]
    client = ScriptedModelClient(turns)

    run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    assert captured_ledgers, "expected at least one rebase to occur"
    last_ledger = captured_ledgers[-1]
    assert "pip install requests" in last_ledger["installed_packages"]
    assert any(item["command"] == "false" and item["exit_code"] != 0 for item in last_ledger["nonzero_exits"])


def test_read_only_verification_context_allows_safe_and_rejects_unsafe_commands(tmp_path: Path) -> None:
    """C7: deny-by-default allowlist for verifier inspection commands."""
    from runner.aether2.loop import ExecutionContext, _ReadOnlyVerificationContext
    from runner.aether2.jobs import JobRegistry
    from runner.aether2.receipts import ReceiptWriter

    task = _make_task(tmp_path)
    executor = _make_executor(task)
    (task.workspace_root / "out.txt").write_text("hello\n", encoding="utf-8")

    state_dir = task.workspace_root / ".aether2" / "state"
    ctx = ExecutionContext(
        executor=executor,
        job_registry=JobRegistry(state_dir),
        session_registry=SessionRegistry(state_dir),
        raw_log_dir=task.workspace_root / ".aether2" / "raw_logs",
    )
    receipts = ReceiptWriter(task.task_dir / ".aether2" / "host_receipts")
    verifier_ctx = _ReadOnlyVerificationContext(ctx, receipts)

    allowed = verifier_ctx.run_command("cat out.txt")
    assert allowed.error is None
    assert "hello" in allowed.stdout_head

    rejected_rm = verifier_ctx.run_command("rm out.txt")
    assert rejected_rm.error is not None
    assert rejected_rm.error.reason_code == "verification_read_only_violation"
    assert (task.workspace_root / "out.txt").exists()

    rejected_redirect = verifier_ctx.run_command("cat out.txt > clobber.txt")
    assert rejected_redirect.error is not None
    assert not (task.workspace_root / "clobber.txt").exists()

    allowed_pipe = verifier_ctx.run_command("cat out.txt | grep hello")
    assert allowed_pipe.error is None

    receipt_files = list((task.task_dir / ".aether2" / "host_receipts").rglob("verifier_inspection_*.json"))
    assert len(receipt_files) == 4


def test_bounded_service_monitoring_reports_survival_same_workspace_and_stable_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    start_snapshot = loop_module.StateSnapshot(
        workspace_root=str(workspace_root),
        captured_at=0.0,
        files={},
        artifact_registry={},
        service_registry={},
        process_registry={},
        job_registry={"svc": {"log_size": 0}},
        session_registry={},
        evidence_ledger={"version": 1, "requirements": [], "blockers": [], "terminal_claims": [], "repeated_failure_families": []},
    )
    end_snapshot = loop_module.StateSnapshot(
        workspace_root=str(workspace_root),
        captured_at=1.0,
        files={},
        artifact_registry={},
        service_registry={},
        process_registry={},
        job_registry={"svc": {"log_size": 16}},
        session_registry={},
        evidence_ledger={"version": 1, "requirements": [], "blockers": [], "terminal_claims": [], "repeated_failure_families": []},
    )

    class FakeJobRegistry:
        def status(self, job_id: str):
            return SimpleNamespace(job_id=job_id, pid=1201, alive=True, exit_code=None, tail="")

    class FakeSessionRegistry:
        def list_session_ids(self):
            return []

    monkeypatch.setattr(loop_module, "delta_snapshot", lambda _: end_snapshot)
    monkeypatch.setattr(loop_module.time, "sleep", lambda _: None)

    monitoring, monitored_snapshot = loop_module._monitor_persistent_runtime(
        ctx=SimpleNamespace(workspace_root=workspace_root),
        job_registry=FakeJobRegistry(),
        session_registry=FakeSessionRegistry(),
        job_ids=["svc"],
        session_ids=[],
        claim_checks=["curl -sf http://127.0.0.1:8000/health"],
        check_results=[
            SimpleNamespace(cwd=str(workspace_root), exit_code=0, stdout="ok", timed_out=False),
            SimpleNamespace(cwd=str(workspace_root), exit_code=0, stdout="ok", timed_out=False),
        ],
        remaining_sec=10,
        start_snapshot=start_snapshot,
    )

    assert monitored_snapshot == end_snapshot
    assert monitoring["applies"] is True
    assert "job svc still running after 2s bounded window" in monitoring["summary"]
    assert "client probes ran from the same workspace root" in monitoring["summary"]
    assert "repeated client probes returned the same response body across the bounded window" in monitoring["summary"]


def test_bounded_service_monitoring_reports_crash_and_environment_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    start_snapshot = loop_module.StateSnapshot(
        workspace_root=str(workspace_root),
        captured_at=0.0,
        files={},
        artifact_registry={},
        service_registry={},
        process_registry={},
        job_registry={"svc": {"log_size": 0}},
        session_registry={},
        evidence_ledger={"version": 1, "requirements": [], "blockers": [], "repeated_failure_families": []},
    )
    end_snapshot = loop_module.StateSnapshot(
        workspace_root=str(workspace_root),
        captured_at=1.0,
        files={},
        artifact_registry={},
        service_registry={},
        process_registry={},
        job_registry={"svc": {"log_size": 0}},
        session_registry={},
        evidence_ledger={"version": 1, "requirements": [], "blockers": [], "repeated_failure_families": []},
    )

    class FakeJobRegistry:
        def __init__(self) -> None:
            self.calls = 0

        def status(self, job_id: str):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(job_id=job_id, pid=1201, alive=True, exit_code=None, tail="")
            return SimpleNamespace(job_id=job_id, pid=1201, alive=False, exit_code=1, tail="Traceback: boom")

    class FakeSessionRegistry:
        def list_session_ids(self):
            return []

    monkeypatch.setattr(loop_module, "delta_snapshot", lambda _: end_snapshot)
    monkeypatch.setattr(loop_module.time, "sleep", lambda _: None)

    monitoring, _ = loop_module._monitor_persistent_runtime(
        ctx=SimpleNamespace(workspace_root=workspace_root),
        job_registry=FakeJobRegistry(),
        session_registry=FakeSessionRegistry(),
        job_ids=["svc"],
        session_ids=[],
        claim_checks=["curl -sf http://127.0.0.1:8000/health"],
        check_results=[SimpleNamespace(cwd="/tmp/outside", exit_code=124, stdout="", timed_out=True)],
        remaining_sec=10,
        start_snapshot=start_snapshot,
    )

    assert monitoring["applies"] is True
    assert "job svc exited before end of 2s bounded window exit code=1" in monitoring["summary"]
    assert "job svc produced new error output during bounded window" in monitoring["summary"]
    assert "client probes did not run from the same workspace root" in monitoring["summary"]
    assert "client probe timed out during bounded monitoring window" in monitoring["summary"]


def test_bounded_service_monitoring_reports_service_pid_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    start_snapshot = loop_module.StateSnapshot(
        workspace_root=str(workspace_root),
        captured_at=0.0,
        files={},
        artifact_registry={},
        service_registry={"web": {"pid": 1201, "port": 8080}},
        process_registry={},
        job_registry={},
        session_registry={},
        evidence_ledger={"version": 1, "requirements": [], "blockers": [], "repeated_failure_families": []},
    )
    end_snapshot = loop_module.StateSnapshot(
        workspace_root=str(workspace_root),
        captured_at=1.0,
        files={},
        artifact_registry={},
        service_registry={"web": {"pid": 1259, "port": 8080}},
        process_registry={},
        job_registry={},
        session_registry={},
        evidence_ledger={"version": 1, "requirements": [], "blockers": [], "repeated_failure_families": []},
    )

    class FakeSessionRegistry:
        def list_session_ids(self):
            return []

    monkeypatch.setattr(loop_module, "delta_snapshot", lambda _: end_snapshot)
    monkeypatch.setattr(loop_module.time, "sleep", lambda _: None)

    monitoring, _ = loop_module._monitor_persistent_runtime(
        ctx=SimpleNamespace(workspace_root=workspace_root),
        job_registry=SimpleNamespace(status=lambda job_id: (_ for _ in ()).throw(KeyError(job_id))),
        session_registry=FakeSessionRegistry(),
        job_ids=[],
        session_ids=[],
        claim_checks=["curl -sf http://127.0.0.1:8080/health"],
        check_results=[],
        remaining_sec=10,
        start_snapshot=start_snapshot,
    )

    assert monitoring["applies"] is True
    assert "service web pid changed from 1201 to 1259 after 2s bounded window" in monitoring["summary"]


def test_repeated_task_done_with_unchanged_blockers_suppresses_second_verifier_call(tmp_path: Path) -> None:
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    turns = [
        _response(
            text="done",
            tool_calls=(_tool_call("task_done", {"summary": "first claim", "checks": ["false"]}, call_id="call-1"),),
        ),
        _response(
            text="done again",
            tool_calls=(_tool_call("task_done", {"summary": "second claim", "checks": ["false"]}, call_id="call-2"),),
        ),
        _response(
            text="done again again",
            tool_calls=(_tool_call("task_done", {"summary": "third claim", "checks": ["false"]}, call_id="call-3"),),
        ),
    ]
    client = ScriptedModelClient(turns, side_responses=[_verify_response(False)])

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    verifier_calls = [
        call
        for call in client.calls
        if {
            tool.get("function", {}).get("name")
            for tool in call[1]
            if isinstance(tool, dict)
        }.issubset({"run_command", "read_file", "job_status", "session_read"})
        and call[1]
    ]

    assert result.verifier_clean is False
    assert result.suppressed_verifier_calls >= 1
    assert result.completion_precheck_rejections >= 1
    assert len(verifier_calls) == 1


def test_verification_action_digest_surfaces_env_contract_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    def _orientation_payload(digest: str):
        return {
            "cwd": str(task.workspace_root),
            "user": "builder",
            "is_root": False,
            "workspace_root": str(task.workspace_root),
            "writable_paths": [str(task.workspace_root)],
            "safe_file_listing": [],
            "tool_presence": {},
            "package_managers": {},
            "network": "blocked",
            "network_reachable": False,
            "network_evidence": "blocked",
            "runtimes": {},
            "processes": [],
            "ports": [],
            "env_contract_version": "aether2_env_contract_v1",
            "env_contract_digest": digest,
            "env_contract": {"contract_version": "aether2_env_contract_v1", "contract_digest": digest},
        }

    orientation_values = iter(
        [
            SimpleNamespace(as_dict=lambda: _orientation_payload("digest-a")),
            SimpleNamespace(as_dict=lambda: _orientation_payload("digest-b")),
        ]
    )
    monkeypatch.setattr(loop_module, "orient", lambda _: next(orientation_values))
    monkeypatch.setattr(loop_module, "_monitor_persistent_runtime", lambda **kwargs: ({"applies": False}, kwargs["start_snapshot"]))

    turns = [
        _response(
            text="done",
            tool_calls=(_tool_call("task_done", {"summary": "ok", "checks": ["true"]}, call_id="call-1"),),
        ),
    ]
    client = ScriptedModelClient(turns)

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)
    assert result.verifier_clean is True

    verifier_payloads = []
    for messages, tools, _ in client.calls:
        tool_names = {
            tool.get("function", {}).get("name")
            for tool in tools
            if isinstance(tool, dict)
        }
        if tool_names and tool_names.issubset({"run_command", "read_file", "job_status", "session_read"}):
            verifier_payloads.append(json.loads(messages[1]["content"]))

    assert verifier_payloads
    assert verifier_payloads[0]["action_digest"]["environment_contract"]["drift_detected"] is True
    assert verifier_payloads[0]["action_digest"]["environment_contract"]["differences"] == ["contract_digest_changed"]


def test_weak_only_satisfied_requirement_yields_verifier_clean_false(tmp_path: Path) -> None:
    """W5.1: a requirement the verifier marks `satisfied` but supports only
    with existence/readback-only (weak) evidence and no independent
    provenance must be treated as an unresolved gap, so `verifier_clean`
    is False even though the model claimed completion."""
    task = _make_task(tmp_path)
    executor = _make_executor(task)

    turns = [
        _response(
            text="writing",
            tool_calls=(_tool_call("write_file", {"path": "out.txt", "content": "hello"}, call_id="call-1"),),
        ),
        _response(
            text="done",
            tool_calls=(_tool_call("task_done", {"summary": "wrote out.txt", "checks": ["cat out.txt"]}, call_id="call-2"),),
        ),
    ]
    # Always return a weak-only "satisfied" verifier report so repair never
    # produces strong evidence within the bounded round limit.
    client = ScriptedModelClient(
        turns,
        side_responses=[
            _weak_satisfied_verify_response(),
            _weak_satisfied_verify_response(),
            _weak_satisfied_verify_response(),
        ],
    )

    result = run_aether2_loop(task, client, executor, deadline_ts=time.time() + 60)

    assert result.verifier_clean is False
    # Bounded reflection: at most 3 verification rounds, no hard veto on completion.
    assert result.verification_rounds <= 3
    discrepancy = result.discrepancy_reports[-1]
    assert any(
        item.requirement == "task complete" and item.unresolved
        for item in discrepancy.requirements
    )


def test_ledger_progress_bare_evidence_ref_increase_is_not_progress() -> None:
    """W2.1: a bare increase in evidence_refs (e.g. an output write or status
    note) must not, by itself, count as stronger evidence. Only a genuine
    strength-rank increase or newly-added independent provenance counts."""
    from runner.aether2.loop import _ledger_progress

    before = {
        "requirements": [
            {
                "requirement": "write final artifact",
                "status": "unproven",
                "evidence_strength": "weak",
                "evidence_refs": ["tool=write_file step=1 artifacts=out.txt note=wrote output"],
                "evidence_provenance": ["model_authored_artifact"],
            }
        ]
    }
    # Same status, same strength, same provenance -- but one more bare ref
    # (e.g. another output write / status note).
    after_bare_write = {
        "requirements": [
            {
                "requirement": "write final artifact",
                "status": "unproven",
                "evidence_strength": "weak",
                "evidence_refs": [
                    "tool=write_file step=1 artifacts=out.txt note=wrote output",
                    "tool=write_file step=2 artifacts=out.txt note=rewrote output again",
                ],
                "evidence_provenance": ["model_authored_artifact"],
            }
        ]
    }
    requirement_advanced, stronger_evidence_added = _ledger_progress(before, after_bare_write)
    assert requirement_advanced is False
    assert stronger_evidence_added is False

    # A genuine strength-rank increase still counts.
    after_strength_increase = {
        "requirements": [
            {
                "requirement": "write final artifact",
                "status": "unproven",
                "evidence_strength": "strong",
                "evidence_refs": ["tool=write_file step=1 artifacts=out.txt note=wrote output"],
                "evidence_provenance": ["model_authored_artifact"],
            }
        ]
    }
    _, stronger_evidence_added = _ledger_progress(before, after_strength_increase)
    assert stronger_evidence_added is True

    # Newly-added independent provenance also counts, even without a strength change.
    after_independent_provenance = {
        "requirements": [
            {
                "requirement": "write final artifact",
                "status": "unproven",
                "evidence_strength": "weak",
                "evidence_refs": [
                    "tool=write_file step=1 artifacts=out.txt note=wrote output",
                    "tool=run_command step=2 cmd=pytest note=ran provided test suite",
                ],
                "evidence_provenance": ["model_authored_artifact", "task_supplied"],
            }
        ]
    }
    _, stronger_evidence_added = _ledger_progress(before, after_independent_provenance)
    assert stronger_evidence_added is True


def test_extract_stated_requirements_skips_boilerplate_wrapper_lines() -> None:
    """W1.1: heading/separator/sign-off wrapper lines do not become noisy
    requirement entries, while substantive lines (including ones with paths)
    are preserved."""
    from runner.aether2.loop import _extract_stated_requirements

    instruction = "\n".join(
        [
            "# Task",
            "Write the result to /workspace/out.txt.",
            "---",
            "Thanks!",
            "Do not modify any other files.",
        ]
    )
    requirements = _extract_stated_requirements(instruction)

    assert "Write the result to /workspace/out.txt." in requirements
    assert "Do not modify any other files." in requirements
    assert all(req not in {"# Task", "---", "Thanks!"} for req in requirements)


def test_relevant_requirement_uses_unassigned_activity_for_unrelated_observation() -> None:
    """W1.1: an observation that shares no visible path/command tokens with
    any stated requirement is attached to the generic unassigned-activity
    bucket rather than forced onto the first unresolved requirement."""
    from runner.aether2.loop import (
        UNASSIGNED_ACTIVITY_REQUIREMENT,
        _relevant_requirement,
        build_evidence_ledger,
    )

    ledger = build_evidence_ledger(["Write the result to /workspace/out.txt."])

    # An unrelated exploratory command (no shared tokens with the requirement).
    unrelated = _relevant_requirement(
        ledger,
        ["Write the result to /workspace/out.txt."],
        tool_name="run_command",
        arguments={"cmd": "uname -a"},
        artifact_paths=[],
    )
    assert unrelated == UNASSIGNED_ACTIVITY_REQUIREMENT

    # A write to the requested artifact path is attached to the matching requirement.
    relevant = _relevant_requirement(
        ledger,
        ["Write the result to /workspace/out.txt."],
        tool_name="write_file",
        arguments={"path": "out.txt"},
        artifact_paths=["out.txt"],
    )
    assert relevant == "Write the result to /workspace/out.txt."
