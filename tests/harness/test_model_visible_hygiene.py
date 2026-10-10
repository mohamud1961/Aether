"""Model-visible requests must not carry experiment, grader or model-name labels."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

import pytest

from aether.envmap_builder import build_envmap_from_task
from aether.execution import CommandResult, MemoryExecutor
from aether.ledger import ExecutionLedger, Receipt
from aether.runtime_ir import ActionRequest, SolverTurn
from aether.selective_judge_advice import MODE_S2_OVERLAP_V1, SelectiveJudgeAdvice
from aether.thin_loop import ThinLoopConfig, run_thin_loop
from aether.trace_aware_judge_advice import TraceAwareJudgeAdvice

FORBIDDEN = (
    "judge", "glm", "grader", "rev9", "benchmark", "s1_", "s2_", "hard_stuck",
    "selective", "trace_aware", "treatment", "arm",
)
_WORD_ONLY = {"arm", "glm", "judge"}
S2_TASK = (
    "Repair workspace/infer.py for a coupled mechanical system observed by asynchronous channels."
)
S2_MODEL = (
    "Align asynchronous channels by linear interpolation between observed samples and "
    "fit only timestamps covered by the\nrequired input channels."
)
CMD = "python3 -m pytest -q"


def _hits(text: str) -> set[str]:
    low = text.lower()
    found = set()
    for token in FORBIDDEN:
        pattern = rf"\b{re.escape(token)}\b" if token in _WORD_ONLY else re.escape(token)
        if re.search(pattern, low):
            found.add(token)
    return found


def _response(request: dict[str, Any]) -> dict[str, Any]:
    answers = {}
    for qid, spec in request["questions"].items():
        choices = list(spec["criteria"])
        answers[qid] = {
            "choice": choices[0],
            "probabilities": {c: 1.0 if i == 0 else 0.0 for i, c in enumerate(choices)},
        }
    return {"result": {"answers": answers}}


def _trace_journal(path: Path, count: int) -> None:
    rows = [{
        "schema_version": "aether.chat_provider_attempt_journal.v1",
        "event_kind": "chat_provider_attempt_journal",
        "attempt": {
            "event_kind": "provider_attempt", "status": "completed",
            "logical_call_id": i, "finish_reason": "tool_calls",
            "raw_provider_output": {"choices": [{"message": {
                "reasoning_content": f"reasoning-{i}",
                "tool_calls": [{"function": {
                    "name": "run_command", "arguments": json.dumps({"command": CMD}),
                }}],
            }}]},
        },
    } for i in range(1, count + 1)]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


class _Hooks:
    def __init__(self) -> None:
        self.messages: list[list[dict[str, Any]]] = []

    def solve(self, messages: list[dict[str, Any]], _compiled: Any) -> SolverTurn:
        self.messages.append(messages)
        n = len(self.messages)
        return SolverTurn(
            kind="act", summary=f"verify {n}", evidence_gap="check",
            actions=(ActionRequest(
                action_id=f"v-{n}", kind="run_command", capability_id="shell",
                arguments={"command": CMD}, intent="verify",
                expected_observation="pass", if_fail_next="inspect",
            ),),
        )


def _run(assistance: Callable[..., Any] | None, signal_mode: str) -> list[list[dict[str, Any]]]:
    executor = MemoryExecutor(workspace_root="/app")
    executor.register_command(CMD, lambda _e, c: CommandResult(c, 0, stdout="all passed"))
    hooks = _Hooks()
    envmap = build_envmap_from_task(
        "/tmp/aether-empty-task-dir", S2_TASK, workspace_root="/app",
        projection_mode="factual_only",
    )
    run_thin_loop(envmap, executor, hooks, config=ThinLoopConfig(
        max_steps=6, max_solver_turns=6, max_accepted_task_actions=6,
        runtime_identity={
            "task_id": "t", "run_id": "hyg", "primary_agent_id": "primary",
            "budgets": {"max_kernel_steps": 6, "max_solver_turns": 6,
                        "max_accepted_task_actions": 6},
        },
        semantic_assistance=assistance,
        solver_completion_signal_mode=signal_mode,
    ))
    return hooks.messages


def _text(messages: list[dict[str, Any]]) -> str:
    return json.dumps(messages, sort_keys=True)


def _packet(messages: list[dict[str, Any]]) -> dict[str, Any]:
    for m in messages:
        content = str(m.get("content", ""))
        if content.startswith("[context_packet]\n"):
            return json.loads(content[len("[context_packet]\n"):])
    raise AssertionError("no context packet")


def _selective() -> SelectiveJudgeAdvice:
    return SelectiveJudgeAdvice(
        _response, model="judge-test", mode=MODE_S2_OVERLAP_V1,
        public_contract={"MODEL.md": S2_MODEL},
    )


def _trace_aware(tmp_path: Path) -> Callable[..., Any]:
    journal = tmp_path / "chat.jsonl"
    _trace_journal(journal, 24)
    advice = TraceAwareJudgeAdvice(_response, model="judge-test", telemetry_journal=journal)
    ledger = ExecutionLedger()
    for step in range(1, 7):
        ledger.record(Receipt(
            receipt_id=f"p-{step}", step=step, kind="run_command", success=True,
            summary="probe", state_change=False,
            payload={"command": CMD, "exit_code": 0, "stdout": "running"},
        ))
    computed = advice(
        task_text="repair the service", ledger=ledger, step=25,
        runtime_identity={"run_id": "hyg"},
    )
    assert computed["status"] == "advice" and computed["items"][0]["head"] == "trace_aware_judge"
    return lambda **_kw: computed


def test_baseline_has_no_forbidden_tokens_to_subtract() -> None:
    baseline = {t for m in _run(None, "control") for t in _hits(_text(m))}
    assert baseline == set()


@pytest.mark.parametrize("kind", ["selective", "trace_aware"])
def test_independent_review_is_neutral(
    kind: str, tmp_path: Path
) -> None:
    assistance = _selective() if kind == "selective" else _trace_aware(tmp_path)
    all_messages = _run(assistance, "verification_authority_v2")
    seen = [m for m in all_messages if "independent_review" in _packet(m)]
    assert seen, "advice never reached the model-visible request"
    for messages in seen:
        packet = _packet(messages)
        assert "semantic_advice" not in packet
        assert set(packet["independent_review"]) == {"instruction", "answers"}
        assert "no access to hidden tests or solutions" in packet["independent_review"]["instruction"]
        assert _hits(_text(messages)) == set()


def test_v2_signal_text_is_neutral() -> None:
    all_messages = _run(None, "verification_authority_v2")
    with_signal = [m for m in all_messages if "completion_signal" in _packet(m)]
    assert with_signal
    for messages in with_signal:
        assert _hits(_text(messages)) == set()
