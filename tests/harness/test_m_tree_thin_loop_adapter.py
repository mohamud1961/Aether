from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aether.context_tree.compactor import MAX_OUTPUT_TOKENS, VIEW_DOC
from aether.context_tree.adapter import ContextTreeAdapter
from aether.envmap_builder import build_envmap_from_task
from aether.execution import CommandResult, MemoryExecutor
from aether.model_hooks import ModelHooks
from aether.model_profile import GLM_RESEARCH_PAR2_PROFILE
from aether.providers.chat_model import ChatCompletionsModelCallable
from aether.research_glm_harbor_agent import _build_m_tree_compactor_provider
from aether.runtime_ir import ActionRequest, CapabilityDescriptor, EnvMap, SolverTurn
from aether.run_deadline import remaining_run_s, run_deadline
from aether.thin_loop import ThinLoopConfig, run_thin_loop
from aether.verifier import ModelVerifierResult, VerifierFinding


TASK = "Read input.txt, write its contents to output.txt, then report the result. " + ("keep this task-local detail. " * 28)


def _synthetic_compactor(
    _request: dict[str, Any], *, route: str, limiter: Any, deadline_monotonic: float,
) -> str:
    if not math.isfinite(deadline_monotonic) or deadline_monotonic <= time.monotonic():
        raise TimeoutError("fake compactor request deadline expired")
    return "synthetic summary"


_synthetic_compactor.supports_finite_deadline = True


def _env(task_prompt: str = TASK) -> EnvMap:
    return EnvMap(
        task_prompt=task_prompt,
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "workspace files", tool_names=("read_file", "write_file"),
            ),
        },
    )


def _env_with_shell(task_prompt: str) -> EnvMap:
    return EnvMap(
        task_prompt=task_prompt,
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "workspace files", tool_names=("read_file", "write_file"),
            ),
            "shell": CapabilityDescriptor(
                "shell", "task-local command execution", tool_names=("run_command",),
            ),
        },
    )


def _action(action_id: str, kind: str, capability_id: str, arguments: dict[str, Any]) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind=kind,
        capability_id=capability_id,
        arguments=arguments,
        intent="inspect the current task state",
        expected_observation="one exact tool result",
        if_fail_next="inspect the returned error",
    )


class _FakeGLMHooks:
    """ModelHooks-shaped fake that makes epoch resets and in-epoch input visible."""

    def __init__(self, *, turns: tuple[SolverTurn, ...]) -> None:
        self.turns = turns
        self.requests: list[list[dict[str, Any]]] = []
        self.schemas: list[tuple[tuple[str, tuple[str, ...]], ...]] = []
        self.reset_calls = 0
        self.verify_calls = 0

    def solve(self, messages: list[dict[str, Any]], compiled: Any) -> SolverTurn:
        self.requests.append(json.loads(json.dumps(messages)))
        self.schemas.append(tuple(compiled.action_schema))
        if any(name == "zoom" for name, _args in compiled.action_schema):
            assert "context_tree" in compiled.selected_capability_ids()
        return self.turns[len(self.requests) - 1]

    def reset_solver_continuity_for_recovery(self) -> bool:
        self.reset_calls += 1
        return True

    def verify(self, *_args: Any, **_kwargs: Any) -> None:
        self.verify_calls += 1
        raise AssertionError("the adapter must leave Thin's verifier policy unchanged")


class _FakeTextProvider:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.requests: list[list[dict[str, Any]]] = []
        self.reset_calls = 0

    def __call__(self, messages: list[dict[str, Any]], *, max_output_tokens: int) -> str:
        self.requests.append(json.loads(json.dumps(messages)))
        return self.responses.pop(0)

    def clear_continuity_scope(self, *, run_id: str, task_id: str) -> None:
        self.reset_calls += 1


def _persistent_action(kind: str, arguments: dict[str, Any], summary: str) -> str:
    return json.dumps({
        "kind": "act",
        "summary": summary,
        "action": {"kind": kind, "arguments": arguments},
    })


def _turns() -> tuple[SolverTurn, ...]:
    return (
        SolverTurn(
            kind="act", summary="I learned the source text.",
            actions=(_action("read-1", "read_file", "filesystem", {"path": "input.txt"}),),
        ),
        SolverTurn(
            kind="act", summary="I used the observed source text.",
            actions=(_action("write-1", "write_file", "filesystem", {
                "path": "output.txt", "content": "source-content",
            }),),
        ),
        SolverTurn(
            kind="act", summary="I checked the earlier task event.",
            actions=(_action("zoom-1", "zoom", "context_tree", {"id": 0, "n": 1}),),
        ),
    )


def test_thin_loop_m_tree_wraps_real_action_results_and_starts_a_fresh_a7_epoch(tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def fake_compactor(
        request: dict[str, Any], *, route: str, limiter: Any, deadline_monotonic: float,
    ) -> str:
        assert math.isfinite(deadline_monotonic) and deadline_monotonic > time.monotonic()
        calls.append((route, str(limiter)))
        assert "reasoning_content" not in json.dumps(request)
        return "task-local summary"
    fake_compactor.supports_finite_deadline = True

    evidence_root = tmp_path / "m_tree_evidence"
    limiter_path = tmp_path / "m_tree_compactor_limiter.json"
    adapter = ContextTreeAdapter(
        raw_task=TASK,
        evidence_root=evidence_root,
        run_id="adapter-run",
        compactor_provider=fake_compactor,
        compactor_route="fake-compactor-route",
        compactor_limiter_path=limiter_path,
        epoch_steps=2,
        request_limit=100_000,
        jobs=2,
        retry_s=0.01,
    )
    hooks = _FakeGLMHooks(turns=_turns())
    executor = MemoryExecutor(
        workspace_root="/app",
        files={"input.txt": "source-content"},
    )

    result = run_thin_loop(
        _env(), executor, hooks,
        config=ThinLoopConfig(
            max_steps=3,
            max_solver_turns=3,
            runtime_identity={"task_id": "synthetic", "run_id": "adapter-run", "primary_agent_id": "solver"},
            probe_runtime_capabilities=False,
            context_tree_adapter=adapter,
        ),
    )

    assert result.status == "step_budget_exhausted", [
        f"{receipt.kind}: {receipt.summary}" for receipt in result.receipts
    ]
    assert not adapter.active
    assert executor.read_file("output.txt") == "source-content"
    assert hooks.verify_calls == 0
    assert hooks.reset_calls == 1
    assert all(("zoom", ("id", "n")) in schema for schema in hooks.schemas)
    assert calls and all(route == "fake-compactor-route" for route, _ in calls)
    assert all(limiter == str(limiter_path) for _, limiter in calls)

    first, same_epoch, fresh_epoch = hooks.requests
    task_index = next(i for i, row in enumerate(first) if row.get("role") == "user" and row.get("content") == TASK)
    view_index = next(i for i, row in enumerate(first) if row.get("role") == "user" and str(row.get("content", "")).startswith("<chat>"))
    packet_index = next(i for i, row in enumerate(first) if str(row.get("content", "")).startswith("[context_packet]\n"))
    assert task_index < view_index < packet_index
    assert any(row.get("role") == "system" and row.get("content") == VIEW_DOC for row in first)
    assert first[task_index]["content"] == TASK
    assert first[:-1] == same_epoch[:-1]
    assert fresh_epoch[:-1] != first[:-1]
    fresh_packet = fresh_epoch[-1]["content"]
    assert fresh_packet.startswith("[context_packet]\n")
    assert "Latest action: write_file" in fresh_packet
    assert "Full result:" in fresh_packet and "source-content" in fresh_packet
    assert any("m_tree_zoom" == row.kind for row in result.receipts)

    event_rows = [
        json.loads(line)
        for line in (evidence_root / "adapter-run" / "log" / "events.jsonl").read_text().splitlines()
    ]
    kinds = [row["kind"] for row in event_rows]
    assert kinds[0] == "task"
    assert "talk" in kinds and "tool" in kinds and "echo" in kinds
    assert any(row["kind"] == "tool" and row["text"].startswith("read_file ") for row in event_rows)
    assert any(row["kind"] == "tool" and row["text"].startswith("write_file ") for row in event_rows)
    assert any(row["kind"] == "tool" and row["text"].startswith("zoom ") for row in event_rows)
    assert "reasoning_content" not in json.dumps(event_rows)
    assert adapter.telemetry()["epoch_boundaries"][0]["reason"] == "epoch_steps"


def test_thin_control_without_adapter_keeps_the_same_request_and_no_tree_state(tmp_path: Path) -> None:
    turns = (_turns()[0],)
    first_hooks = _FakeGLMHooks(turns=turns)
    second_hooks = _FakeGLMHooks(turns=turns)
    first = run_thin_loop(
        _env(), MemoryExecutor(workspace_root="/app", files={"input.txt": "source-content"}),
        first_hooks,
        config=ThinLoopConfig(
            max_steps=1, max_solver_turns=1,
            runtime_identity={"task_id": "synthetic", "run_id": "control", "primary_agent_id": "solver"},
            probe_runtime_capabilities=False,
        ),
    )
    second = run_thin_loop(
        _env(), MemoryExecutor(workspace_root="/app", files={"input.txt": "source-content"}),
        second_hooks,
        config=ThinLoopConfig(
            max_steps=1, max_solver_turns=1,
            runtime_identity={"task_id": "synthetic", "run_id": "control", "primary_agent_id": "solver"},
            probe_runtime_capabilities=False,
            context_tree_adapter=None,
        ),
    )

    assert first.status == second.status == "step_budget_exhausted"
    assert first.requests[0]["messages"] == second.requests[0]["messages"]
    assert first.requests[0]["action_schema_sha256"] == second.requests[0]["action_schema_sha256"]
    assert "context_tree" not in first.requests[0]
    assert "context_tree" not in second.requests[0]
    assert "context_tree" not in first.requests[0]["action_schema_sha256"]
    assert first_hooks.verify_calls == second_hooks.verify_calls == 0
    assert not (tmp_path / "m_tree_evidence").exists()


def test_thin_loop_m_tree_uses_real_model_parser_and_replays_zoom_result_into_next_context(
    tmp_path: Path,
) -> None:
    task = "Read input.txt, copy it to output.txt, and inspect the task event."
    source_content = "source-content-" * 48
    provider = _FakeTextProvider(
        _persistent_action("read_file", {"path": "input.txt"}, "Read the source file."),
        _persistent_action(
            "write_file", {"path": "output.txt", "content": source_content},
            "Copy the observed source text.",
        ),
        _persistent_action("zoom", {"id": 0, "n": 1}, "Inspect the task line."),
        _persistent_action("zoom", {"id": 0, "n": 1}, "Recheck the task line."),
    )
    hooks = ModelHooks(
        provider,
        lambda _messages, **_kwargs: "{}",
        run_id="parser-run",
        task_id="synthetic-task",
        solver_max_output_tokens=1_000,
    )
    compactor_calls: list[tuple[str, str]] = []
    limiter_path = tmp_path / "parser-limiter.json"

    def fake_compactor(
        _request: dict[str, Any], *, route: str, limiter: Any, deadline_monotonic: float,
    ) -> str:
        assert math.isfinite(deadline_monotonic) and deadline_monotonic > time.monotonic()
        compactor_calls.append((route, str(limiter)))
        return "synthetic summary of the long source result"
    fake_compactor.supports_finite_deadline = True

    adapter = ContextTreeAdapter(
        raw_task=task,
        evidence_root=tmp_path / "parser-evidence",
        run_id="parser-run",
        compactor_provider=fake_compactor,
        compactor_route="fake-compactor-route",
        compactor_limiter_path=limiter_path,
        epoch_steps=1,
        request_limit=100_000,
        jobs=1,
        retry_s=0.01,
    )
    executor = MemoryExecutor(workspace_root="/app", files={"input.txt": source_content})
    result = run_thin_loop(
        _env(task),
        executor,
        hooks,
        config=ThinLoopConfig(
            max_steps=4,
            max_solver_turns=4,
            runtime_identity={
                "task_id": "synthetic-task", "run_id": "parser-run",
                "primary_agent_id": "solver",
            },
            probe_runtime_capabilities=False,
            context_tree_adapter=adapter,
        ),
    )

    assert result.status == "step_budget_exhausted"
    assert not adapter.active
    assert len(provider.requests) == 4
    assert len(result.requests) == 4
    assert provider.reset_calls == 3
    assert executor.read_file("output.txt") == source_content
    assert compactor_calls
    assert all(route == "fake-compactor-route" for route, _ in compactor_calls)
    assert all(limiter == str(limiter_path) for _, limiter in compactor_calls)

    zoom_receipts = [receipt for receipt in result.receipts if receipt.kind == "m_tree_zoom"]
    assert len(zoom_receipts) == 2
    assert all(receipt.success for receipt in zoom_receipts)
    assert zoom_receipts[0].payload["result"] == f"0+0|task: {task}"

    events_path = tmp_path / "parser-evidence" / "parser-run" / "log" / "events.jsonl"
    event_rows = [json.loads(line) for line in events_path.read_text().splitlines()]
    assert [row["kind"] for row in event_rows[:4]] == ["task", "talk", "tool", "echo"]
    assert [row["kind"] for row in event_rows[8:10]] == ["tool", "echo"]
    assert event_rows[8]["text"].startswith('zoom {"id":0,"n":1}')
    assert event_rows[9]["text"] == f"0+0|task: {task}"

    second_model_request = provider.requests[3]
    second_model_text = "\n".join(str(row.get("content") or "") for row in second_model_request)
    assert "8+1|tool: zoom" in second_model_text
    assert "9+1|echo: 0+0|task:" in second_model_text
    assert "Latest action: zoom" in second_model_text
    assert f"Full result:\n0+0|task: {task}" in second_model_text
    assert all(row.get("role") != "tool" for row in second_model_request)


def test_control_model_parser_rejects_m_tree_zoom_without_the_adapter() -> None:
    task = "Synthetic control task with no context-tree capability."
    zoom_output = _persistent_action("zoom", {"id": 0, "n": 1}, "Try to open a history line.")
    provider = _FakeTextProvider(zoom_output, zoom_output, zoom_output)
    hooks = ModelHooks(
        provider,
        lambda _messages, **_kwargs: "{}",
        run_id="control-parser-run",
        task_id="synthetic-task",
        solver_max_output_tokens=1_000,
    )

    result = run_thin_loop(
        _env(task),
        MemoryExecutor(workspace_root="/app"),
        hooks,
        config=ThinLoopConfig(
            max_steps=1,
            max_solver_turns=3,
            runtime_identity={
                "task_id": "synthetic-task", "run_id": "control-parser-run",
                "primary_agent_id": "solver",
            },
            probe_runtime_capabilities=False,
        ),
    )

    assert result.status == "solver_protocol_failure"
    assert len(provider.requests) == 3
    assert len(result.requests) == 3
    assert all("context_tree" not in request for request in result.requests)
    assert not any(receipt.kind == "m_tree_zoom" for receipt in result.receipts)


def test_m_tree_notes_record_challenger_hook_protocol_feedback_and_action_refusal(tmp_path: Path) -> None:
    task = "Write only files inside the task workspace."
    correction_provider = _FakeTextProvider(
        "not a valid solver turn",
        _persistent_action("write_file", {"path": "../outside.txt", "content": "x"}, "Try the write."),
    )
    hooks = ModelHooks(
        correction_provider,
        lambda _messages, **_kwargs: "{}",
        run_id="note-protocol-run",
        task_id="synthetic-task",
        solver_max_output_tokens=1_000,
    )
    adapter = ContextTreeAdapter(
        raw_task=task,
        evidence_root=tmp_path / "note-protocol-evidence",
        run_id="note-protocol-run",
        compactor_provider=_synthetic_compactor,
        compactor_limiter_path=tmp_path / "note-protocol-limiter.json",
        jobs=1,
        retry_s=0.01,
    )
    challenger_note = "CHALLENGER public card: the copy is not verified yet."
    adapter.record_note(challenger_note)

    result = run_thin_loop(
        _env(task), MemoryExecutor(workspace_root="/app"), hooks,
        config=ThinLoopConfig(
            max_steps=1,
            max_solver_turns=2,
            runtime_identity={
                "task_id": "synthetic-task", "run_id": "note-protocol-run",
                "primary_agent_id": "solver",
            },
            probe_runtime_capabilities=False,
            context_tree_adapter=adapter,
        ),
    )

    assert result.status == "step_budget_exhausted"
    assert len(correction_provider.requests) == 2
    assert any(receipt.kind == "action_validation" for receipt in result.receipts)
    events_path = (
        tmp_path / "note-protocol-evidence" / "note-protocol-run"
        / "log" / "events.jsonl"
    )
    event_rows = [json.loads(line) for line in events_path.read_text().splitlines()]
    note_texts = [row["text"] for row in event_rows if row["kind"] == "note"]
    sent_feedback = correction_provider.requests[1][-1]["content"]
    assert challenger_note in note_texts
    assert sent_feedback in note_texts
    assert any("invalid workspace path" in note for note in note_texts)
    assert "reasoning_content" not in json.dumps(event_rows)
    assert not adapter.active


def test_m_tree_notes_record_completion_signal_j_ev_projection_and_gate(tmp_path: Path) -> None:
    task = "Run verification and report the observed result."
    judge_advice = {
        "schema": "aether.semantic_advice.v1",
        "authority": "advisory_only",
        "items": [{
            "head": "trace_aware_judge",
            "answers": {
                "question-1": {
                    "choice": "relevant",
                    "probabilities": {
                        "relevant": 0.8, "irrelevant": 0.1, "uncertain": 0.1,
                    },
                },
            },
        }],
    }
    hooks = _FakeGLMHooks(turns=(
        SolverTurn(
            kind="act", summary="Run the verification command.",
            actions=(_action("verify-1", "run_command", "shell", {
                "command": "pytest -q",
            }),),
        ),
        SolverTurn(
            kind="finish_intent", summary="The verification result supports completion.",
            claim="The verification result supports completion.",
            evidence_refs=("unknown-synthetic-ref",),
        ),
    ))
    executor = MemoryExecutor(workspace_root="/app")
    executor.register_command(
        "pytest -q",
        lambda _executor, command: CommandResult(
            command=command, exit_code=0, stdout="1 passed",
        ),
    )
    adapter = ContextTreeAdapter(
        raw_task=task,
        evidence_root=tmp_path / "note-completion-evidence",
        run_id="note-completion-run",
        compactor_provider=_synthetic_compactor,
        compactor_limiter_path=tmp_path / "note-completion-limiter.json",
        jobs=1,
        retry_s=0.01,
    )

    result = run_thin_loop(
        _env_with_shell(task), executor, hooks,
        config=ThinLoopConfig(
            max_steps=2,
            max_solver_turns=2,
            runtime_identity={
                "task_id": "synthetic-task", "run_id": "note-completion-run",
                "primary_agent_id": "solver",
            },
            probe_runtime_capabilities=False,
            solver_completion_signal_mode="verification_v1",
            semantic_assistance=lambda **_kwargs: judge_advice,
            context_tree_adapter=adapter,
        ),
    )

    assert result.status == "step_budget_exhausted"
    assert any(receipt.kind == "thin_submission_blocked" for receipt in result.receipts)
    events_path = (
        tmp_path / "note-completion-evidence" / "note-completion-run"
        / "log" / "events.jsonl"
    )
    event_rows = [json.loads(line) for line in events_path.read_text().splitlines()]
    note_texts = [row["text"] for row in event_rows if row["kind"] == "note"]
    expected_review = {
        "instruction": (
            "Independent review of the current public evidence; it has no access to hidden "
            "tests or solutions. Weigh it against your own observations."
        ),
        "answers": {
            "question-1": {
                "choice": "relevant",
                "probabilities": {
                    "relevant": 0.8, "irrelevant": 0.1, "uncertain": 0.1,
                },
            },
        },
    }
    assert json.dumps(expected_review, ensure_ascii=False, sort_keys=True, separators=(",", ":")) in note_texts
    assert any('"schema":"aether.completion_signal.v1"' in note for note in note_texts)
    assert "The verification result supports completion." in note_texts
    assert any("Thin submission blocked" in note for note in note_texts)
    assert "reasoning_content" not in json.dumps(event_rows)
    assert not adapter.active


def test_m_tree_notes_persist_verification_result_and_completion(tmp_path: Path) -> None:
    task = "Change app.py to x=2 and finish."

    def latest_read_ref(messages: list[dict[str, Any]]) -> str:
        marker = "[context_packet]\n"
        packet = next(
            json.loads(str(row["content"])[len(marker):])
            for row in messages
            if str(row.get("content") or "").startswith(marker)
        )
        refs = [
            str(row["evidence_ref"])
            for row in packet.get("evidence_index", ())
            if isinstance(row, dict)
            and row.get("evidence_type") == "read_file"
            and row.get("currentness") == "latest_primary_result"
            and row.get("evidence_ref")
            and row.get("completion_evidence_eligible", True)
        ]
        assert refs
        return refs[-1]

    class ReviewHooks:
        def __init__(self) -> None:
            self.solve_calls = 0
            self.verify_calls = 0

        def solve(self, messages: list[dict[str, Any]], _compiled: Any) -> SolverTurn:
            self.solve_calls += 1
            if self.solve_calls == 1:
                return SolverTurn(
                    kind="act", summary="Read the current file.",
                    actions=(_action("review-read-1", "read_file", "filesystem", {
                        "path": "app.py",
                    }),),
                )
            if self.solve_calls == 2:
                return SolverTurn(
                    kind="finish_intent", summary="Request review of the candidate.",
                    claim="The candidate is complete.",
                    evidence_refs=(latest_read_ref(messages),),
                )
            marker = "[context_packet]\n"
            packet = next(
                json.loads(str(row["content"])[len(marker):])
                for row in messages
                if str(row.get("content") or "").startswith(marker)
            )
            assert packet.get("open_completion_findings")
            if self.solve_calls == 3:
                return SolverTurn(
                    kind="act", summary="Repair the reviewed value.",
                    actions=(_action("review-write-1", "write_file", "filesystem", {
                        "path": "app.py", "content": "x=2\n",
                    }),),
                )
            if self.solve_calls == 4:
                return SolverTurn(
                    kind="act", summary="Read the repaired file.",
                    actions=(_action("review-read-2", "read_file", "filesystem", {
                        "path": "app.py",
                    }),),
                )
            return SolverTurn(
                kind="finish_intent", summary="Request a fresh review.",
                claim="The repaired candidate is complete.",
                evidence_refs=(latest_read_ref(messages),),
            )

        def verify(self, packet: dict[str, Any], *_args: Any, **_kwargs: Any) -> ModelVerifierResult:
            self.verify_calls += 1
            if self.verify_calls == 1:
                return ModelVerifierResult(
                    verdict="needs_repair",
                    confidence="high",
                    summary="The production value is still old.",
                    findings=(VerifierFinding(
                        finding_id="synthetic-old-value",
                        created_step=0,
                        verdict="needs_repair",
                        priority="blocking",
                        summary="app.py still contains the old value.",
                        evidence=("current file inspection",),
                        applies_to=("app.py",),
                        owner="model_verifier",
                        observed_task_state_generation=int(
                            packet.get("task_state_generation", 0) or 0
                        ),
                    ),),
                )
            return ModelVerifierResult(
                verdict="completed",
                confidence="high",
                summary="The repaired candidate is current.",
            )

    env = build_envmap_from_task(
        str(tmp_path / "no-task-directory"), task,
        workspace_root="/app", projection_mode="factual_only",
    )
    executor = MemoryExecutor(workspace_root="/app", files={"app.py": "x=1\n"})
    hooks = ReviewHooks()
    adapter = ContextTreeAdapter(
        raw_task=task,
        evidence_root=tmp_path / "verification-evidence",
        run_id="verification-note-run",
        compactor_provider=_synthetic_compactor,
        compactor_limiter_path=tmp_path / "verification-limiter.json",
        jobs=1,
        retry_s=0.01,
    )

    result = run_thin_loop(
        env, executor, hooks,
        config=ThinLoopConfig(
            max_steps=8,
            max_solver_turns=8,
            max_accepted_task_actions=4,
            runtime_identity={
                "task_id": "synthetic-review-task",
                "run_id": "verification-note-run",
                "primary_agent_id": "solver",
            },
            probe_runtime_capabilities=False,
            terminal_verifier_mode="terminal_verifier_v1",
            context_tree_adapter=adapter,
        ),
    )

    assert result.status == "submitted", [
        f"{receipt.kind}: {receipt.summary}" for receipt in result.receipts
    ]
    assert hooks.verify_calls == 2
    events_path = (
        tmp_path / "verification-evidence" / "verification-note-run"
        / "log" / "events.jsonl"
    )
    event_rows = [json.loads(line) for line in events_path.read_text().splitlines()]
    note_texts = [row["text"] for row in event_rows if row["kind"] == "note"]
    verifier_notes = []
    for note in note_texts:
        try:
            value = json.loads(note)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "verdict" in value and "findings" in value:
            verifier_notes.append(value)
    assert any(
        row["verdict"] == "needs_repair"
        and row["summary"] == "The production value is still old."
        and row["findings"][0]["summary"] == "app.py still contains the old value."
        for row in verifier_notes
    )
    assert any(
        row["verdict"] == "completed"
        and row["summary"] == "The repaired candidate is current."
        for row in verifier_notes
    )
    assert "The repaired candidate is complete." in note_texts
    assert "reasoning_content" not in json.dumps(event_rows)
    assert not adapter.active


def test_m_tree_request_overflow_does_not_count_an_undispatched_solver_turn(tmp_path: Path) -> None:
    task = "Synthetic request that exceeds a one-token M-TREE request limit."
    adapter = ContextTreeAdapter(
        raw_task=task,
        evidence_root=tmp_path / "overflow-evidence",
        run_id="overflow-run",
        compactor_provider=_synthetic_compactor,
        compactor_limiter_path=tmp_path / "overflow-limiter.json",
        request_limit=1,
        jobs=1,
        retry_s=0.01,
    )
    hooks = _FakeGLMHooks(turns=(_turns()[0],))

    result = run_thin_loop(
        _env(task), MemoryExecutor(workspace_root="/app", files={"input.txt": "x"}), hooks,
        config=ThinLoopConfig(
            max_steps=1,
            max_solver_turns=1,
            runtime_identity={
                "task_id": "synthetic-task", "run_id": "overflow-run",
                "primary_agent_id": "solver",
            },
            probe_runtime_capabilities=False,
            context_tree_adapter=adapter,
        ),
    )

    assert result.status == "m_tree_epoch_overflow"
    assert hooks.requests == []
    assert result.accounting is not None
    assert result.accounting.get("solver_provider_turns", 0) == 0
    assert not adapter.active


def test_m_tree_continuity_reset_failure_does_not_count_undispatched_turn(tmp_path: Path) -> None:
    task = "Read the current task file and report what it contains."
    adapter = ContextTreeAdapter(
        raw_task=task,
        evidence_root=tmp_path / "reset-evidence",
        run_id="reset-run",
        compactor_provider=_synthetic_compactor,
        compactor_limiter_path=tmp_path / "reset-limiter.json",
        epoch_steps=1,
        jobs=1,
        retry_s=0.01,
    )

    class ResetFailHooks(_FakeGLMHooks):
        def reset_solver_continuity_for_recovery(self) -> bool:
            self.reset_calls += 1
            return False

    hooks = ResetFailHooks(turns=(_turns()[0],))
    result = run_thin_loop(
        _env(task), MemoryExecutor(workspace_root="/app", files={"input.txt": "x"}), hooks,
        config=ThinLoopConfig(
            max_steps=3,
            max_solver_turns=3,
            runtime_identity={
                "task_id": "synthetic-task", "run_id": "reset-run",
                "primary_agent_id": "solver",
            },
            probe_runtime_capabilities=False,
            context_tree_adapter=adapter,
        ),
    )

    assert result.status == "m_tree_continuity_reset_failed"
    assert hooks.reset_calls == 1
    assert len(hooks.requests) == 1
    assert result.accounting is not None
    assert result.accounting.get("solver_provider_turns", 0) == 1
    failure = next(row for row in result.receipts if row.kind == "m_tree_continuity_reset_failed")
    assert failure.payload["provider_call_dispatched"] is False
    assert not adapter.active


def test_m_tree_production_compactor_wrapper_propagates_sdk_timeout_and_cancellation(
    tmp_path: Path,
) -> None:
    class TimeoutRecordingTransport:
        def __init__(self) -> None:
            self.requests: list[dict[str, Any]] = []

        def create(self, **request: Any) -> dict[str, Any]:
            self.requests.append(dict(request))
            return {
                "id": "bounded-compactor-response",
                "choices": [{
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "task summary"},
                }],
                "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
            }

    transport = TimeoutRecordingTransport()
    chat_callable = ChatCompletionsModelCallable(
        transport=transport,
        deployment="FW-GLM-5.3-Flash-par-2",
        role="solver",
        effort="medium",
        tools=(),
        native_persistent_tools=False,
        provider_timeout_s=30.0,
    )
    limiter_path = tmp_path / "limiter.json"
    provider = _build_m_tree_compactor_provider(
        SimpleNamespace(profile=GLM_RESEARCH_PAR2_PROFILE, endpoint="https://example.invalid"),
        limiter_path=limiter_path,
        run_id="synthetic-run",
        task_id="synthetic-task",
        callable_factory=lambda *_args, **_kwargs: chat_callable,
    )
    cancellation_event = threading.Event()

    bind = getattr(provider, "bind_run_cancellation", None)
    assert callable(bind)
    bind(cancellation_event)

    started = time.monotonic()
    deadline = started + 5.0
    response = provider(
        {
            "model": "FW-GLM-5.3-Flash-par-2",
            "effort": "medium",
            "messages": [{"role": "user", "content": "summarize"}],
        },
        route="FW-GLM-5.3-Flash-par-2",
        limiter=str(limiter_path),
        deadline_monotonic=deadline,
    )

    assert provider.supports_finite_deadline is True
    assert chat_callable._run_cancellation_event is cancellation_event
    assert response["text"] == "task summary"
    assert len(transport.requests) == 1
    assert transport.requests[0]["max_tokens"] == MAX_OUTPUT_TOKENS == 16_384
    assert transport.requests[0]["reasoning_effort"] == "medium"
    assert 0 < transport.requests[0]["timeout"] <= deadline - started


def test_m_tree_rejects_provider_without_finite_deadline_contract_before_evidence_creation(
    tmp_path: Path,
) -> None:
    dispatched = False

    def unbounded_provider(
        _request: dict[str, Any], *, route: str, limiter: Any, deadline_monotonic: float,
    ) -> str:
        nonlocal dispatched
        dispatched = True
        return "unbounded response"

    evidence_root = tmp_path / "must-not-exist"
    with pytest.raises(TypeError, match="finite deadline enforcement"):
        ContextTreeAdapter(
            raw_task="task",
            evidence_root=evidence_root,
            run_id="unbounded-provider",
            compactor_provider=unbounded_provider,
            compactor_limiter_path=tmp_path / "limiter.json",
        )
    assert not dispatched
    assert not evidence_root.exists()


@pytest.mark.parametrize("stop_kind", ["cancel", "deadline"])
def test_m_tree_settle_stops_on_cancellation_or_deadline_and_closes_workers(
    tmp_path: Path, stop_kind: str,
) -> None:
    task = "A long synthetic task that needs compaction before any solver request. " + ("x" * 700)
    cancel_event = threading.Event()
    compactor_started = threading.Event()
    provider = _FakeTextProvider("{}")

    class StopAwareCompactor:
        supports_finite_deadline = True

        def __init__(self) -> None:
            self.cancellation_event: threading.Event | None = None
            self.cancellation_seen = threading.Event()
            self.deadline_seen = threading.Event()
            self.deadline_expired = threading.Event()
            self.initial_remaining_s: float | None = None
            self.calls = 0

        def bind_run_cancellation(self, event: threading.Event | None) -> None:
            self.cancellation_event = event

        def __call__(
            self, _request: dict[str, Any], *, route: str, limiter: Any,
            deadline_monotonic: float,
        ) -> str:
            self.calls += 1
            assert math.isfinite(deadline_monotonic) and deadline_monotonic > time.monotonic()
            compactor_started.set()
            if stop_kind == "cancel":
                assert self.cancellation_event is cancel_event
                assert self.cancellation_event.wait(timeout=1.0)
                self.cancellation_seen.set()
                return "late response after cooperative cancellation"

            self.initial_remaining_s = remaining_run_s()
            self.deadline_seen.set()
            if self.initial_remaining_s is None:
                return "worker did not receive the task deadline"
            while True:
                remaining = remaining_run_s()
                if remaining is None or remaining <= 0.0:
                    self.deadline_expired.set()
                    return "late response after task deadline"
                time.sleep(min(remaining, 0.01))

    compactor = StopAwareCompactor()

    adapter = ContextTreeAdapter(
        raw_task=task,
        evidence_root=tmp_path / f"settle-{stop_kind}-evidence",
        run_id=f"settle-{stop_kind}-run",
        compactor_provider=compactor,
        compactor_limiter_path=tmp_path / f"settle-{stop_kind}-limiter.json",
        jobs=1,
        retry_s=0.01,
    )
    hooks = ModelHooks(
        provider,
        lambda _messages, **_kwargs: "{}",
        run_id=f"settle-{stop_kind}-run",
        task_id="synthetic-task",
        solver_max_output_tokens=1_000,
    )

    def cancel_after_start() -> None:
        assert compactor_started.wait(timeout=1.0)
        cancel_event.set()

    canceller = None
    if stop_kind == "cancel":
        canceller = threading.Thread(target=cancel_after_start, daemon=True)
        canceller.start()
    config = ThinLoopConfig(
        max_steps=1,
        max_solver_turns=1,
        runtime_identity={
            "task_id": "synthetic-task", "run_id": f"settle-{stop_kind}-run",
            "primary_agent_id": "solver",
        },
        run_started_monotonic=time.monotonic(),
        cancellation_event=cancel_event,
        probe_runtime_capabilities=False,
        context_tree_adapter=adapter,
    )

    run_started = time.monotonic()
    if stop_kind == "deadline":
        with run_deadline(run_started + 0.35):
            result = run_thin_loop(
                _env(task), MemoryExecutor(workspace_root="/app"), hooks, config=config,
            )
    else:
        result = run_thin_loop(
            _env(task), MemoryExecutor(workspace_root="/app"), hooks, config=config,
        )

    if canceller is not None:
        canceller.join(timeout=1.0)
        assert not canceller.is_alive()
    assert compactor_started.is_set()
    assert result.status == "timeout"
    assert time.monotonic() - run_started < 1.0
    assert provider.requests == []
    assert compactor.calls == 1
    if stop_kind == "cancel":
        assert compactor.cancellation_seen.is_set()
    else:
        assert compactor.deadline_seen.is_set()
        assert compactor.initial_remaining_s is not None
        assert compactor.initial_remaining_s > 0
        assert compactor.deadline_expired.is_set()
    node_rows = [
        json.loads(line)
        for line in (
            tmp_path / f"settle-{stop_kind}-evidence" / f"settle-{stop_kind}-run"
            / "tree" / "nodes.jsonl"
        ).read_text().splitlines()
    ]
    assert not any(row.get("source") == "compactor" for row in node_rows)
    assert not adapter.active
    assert not any(thread.name.startswith("m-tree") for thread in threading.enumerate())


def test_thin_loop_closes_started_context_tree_when_request_estimation_raises(tmp_path: Path) -> None:
    task = "Synthetic task for adapter cleanup."
    adapter = ContextTreeAdapter(
        raw_task=task,
        evidence_root=tmp_path / "cleanup-evidence",
        run_id="cleanup-run",
        compactor_provider=_synthetic_compactor,
        compactor_limiter_path=tmp_path / "cleanup-limiter.json",
        request_estimator=lambda _request: (_ for _ in ()).throw(RuntimeError("estimate failed")),
        jobs=1,
        retry_s=0.01,
    )
    hooks = _FakeGLMHooks(turns=())
    with pytest.raises(RuntimeError, match="estimate failed"):
        run_thin_loop(
            _env(task),
            MemoryExecutor(workspace_root="/app"),
            hooks,
            config=ThinLoopConfig(
                max_steps=1,
                max_solver_turns=1,
                runtime_identity={
                    "task_id": "synthetic-task", "run_id": "cleanup-run",
                    "primary_agent_id": "solver",
                },
                probe_runtime_capabilities=False,
                context_tree_adapter=adapter,
            ),
        )

    assert not adapter.active
    events_path = tmp_path / "cleanup-evidence" / "cleanup-run" / "log" / "events.jsonl"
    assert json.loads(events_path.read_text().splitlines()[0])["kind"] == "task"
