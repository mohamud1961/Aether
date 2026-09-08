from __future__ import annotations

import json

import pytest

from aether.execution import MemoryExecutor
from aether.kernel import AetherNextKernel, KernelResult
from aether.kernel_verifier import _inspection_evidence_summary
from aether.model_hooks import ModelHooks
from aether.pcr_context import evidence_alias
from aether.ledger import ExecutionLedger, Receipt
from aether.result_metrics import model_parse_errors_for_row, parse_protocol_metrics, repeated_action_metrics
from aether.runtime_ir import ActionRequest, CapabilityDescriptor, CompiledRuntime, EnvMap, SolverTurn
from aether.verifier import ModelVerifierResult, classify_verifier_outcome, parse_model_verifier_result
from tests.test_prompt_cache_stability import _CapturingHooks, _env


def test_final_rendered_solver_prompt_uses_completion_language_not_verifier_psychology() -> None:
    hooks = _CapturingHooks()
    AetherNextKernel(max_steps=1).run(_env(), MemoryExecutor(), hooks)
    rendered = "\n".join(message["content"] for message in hooks.captured[0])
    lowered = rendered.lower()

    for forbidden in (
        "active_verifier_findings",
        "verifier feedback",
        "verifier finding",
        "reviewer",
        "judge",
        "grader",
        "hidden test",
    ):
        assert forbidden not in lowered
    assert "open_completion_findings" in lowered
    assert "use finish_intent when you believe the current candidate is complete" in lowered
    assert "use finish when you decide the task is complete" in lowered
    assert "finish actually finishes and never implicitly starts review" in lowered
    assert "evidence references" in lowered
    assert "completion must be supported by observed evidence" in lowered


def test_result_metrics_aggregate_parse_errors_from_receipts_not_hook_state() -> None:
    result = KernelResult(
        status="incomplete",
        step=3,
        reconfigurations=0,
        receipts=(
            Receipt("step-0:solver_parse_error", 0, "solver_parse_error", False, "bad json", failure_class="solver_protocol_error", payload={"error": "bad json", "retry_attempted": True}),
            Receipt("step-0:solver_parse_error_retry", 0, "solver_parse_error", False, "still bad", failure_class="solver_protocol_error", payload={"error": "still bad", "retry_attempted": False}),
            Receipt("step-1:cmd", 1, "run_command", True, "ran", payload={"command": "echo ok"}),
        ),
    )

    metrics = parse_protocol_metrics(result)
    assert metrics["solver_parse_error_count"] == 2
    assert metrics["parse_repair_attempts"] == 1
    assert metrics["parse_repair_failures"] == 1
    assert metrics["first_valid_action_step"] == 1
    row_errors = model_parse_errors_for_row(result, hook_errors=[])
    assert len(row_errors) == 2
    assert row_errors[0]["kind"] == "solver_parse_error"


def test_repeated_action_metrics_are_information_gain_oriented() -> None:
    result = KernelResult(
        status="incomplete",
        step=4,
        reconfigurations=0,
        receipts=(
            Receipt("c1", 0, "run_command", True, "ran", payload={"command": "pytest -q"}),
            Receipt("c2", 1, "run_command", True, "ran", payload={"command": "pytest -q"}),
            Receipt("s1", 2, "model_verifier_skipped", True, "skip", payload={"reason": "active_findings_without_intervening_evidence"}),
        ),
    )
    metrics = repeated_action_metrics(result)
    assert metrics["repeated_command_count"] == 1
    assert metrics["submit_without_new_evidence_count"] == 1


def test_repeated_action_context_guidance_does_not_call_hypothesis_wrong() -> None:
    class RepeatHooks(_CapturingHooks):
        def solve(self, messages, compiled):
            self.captured.append([dict(m) for m in messages])
            if len(self.captured) <= 2:
                return SolverTurn(
                    kind="act",
                    summary="repeat command intentionally",
                    actions=(ActionRequest(action_id="repeat", kind="run_command", capability_id="shell", arguments={"command": "echo same"}, intent="repeat command", expected_observation="same output", if_fail_next="stop repeating"),),
                evidence_gap="The next action must resolve the current evidence gap",
                )
            return SolverTurn(kind="submit_outcome", summary="done")

    hooks = RepeatHooks()
    AetherNextKernel(max_steps=3).run(_env(), MemoryExecutor(), hooks)
    packet = json.loads(hooks.captured[-1][-1]["content"].split("\n", 1)[1])
    assert "repeat_efficiency_guidance" not in packet
    assert "no_progress_controls" not in packet
    assert "action_constraints" not in packet


def test_inspection_evidence_summary_and_verdict_taxonomy_are_precise() -> None:
    receipts = (
        Receipt(
            "inspect-1",
            2,
            "model_verifier_inspection",
            True,
            "inspection executed",
            payload={
                "requests": [{"kind": "read_file", "path": "/app/out.txt"}],
                "results": [{"kind": "read_file", "path": "/app/out.txt", "bytes": 12, "content_hash": "abc", "read_only": True}],
            },
        ),
    )
    summary = _inspection_evidence_summary(receipts)
    assert summary["inspection_count"] == 1
    assert summary["inspection_tools_used"] == ["read_file"]
    assert summary["inspected_items"][0]["path"] == "/app/out.txt"

    result = parse_model_verifier_result({
        "verdict": "blocked_by_tooling",
        "confidence": "medium",
        "summary": "Probe ran but output was inconclusive",
        "findings": [{"summary": "probe output inconclusive", "evidence": ["ambiguous response"]}],
    })
    assert classify_verifier_outcome(result, inspection_summary=summary) == "probe_inconclusive"


def test_model_verifier_result_accepts_precise_new_taxonomy() -> None:
    result = ModelVerifierResult(
        verdict="incomplete_semantic_mismatch",
        summary="output values are wrong",
    )
    assert result.verdict == "incomplete_semantic_mismatch"


def test_kernel_maintains_compact_world_state_for_verifier_packet() -> None:
    class Hooks(_CapturingHooks):
        def __init__(self) -> None:
            super().__init__()
            self.verifier_packets: list[dict] = []

        def solve(self, messages, compiled):
            if self._step == 0:
                self._step += 1
                return SolverTurn(
                    kind="act",
                    summary="write the requested artifact",
                    actions=(ActionRequest(
                        action_id="write",
                        kind="write_file",
                        capability_id="filesystem",
                        arguments={"path": "out.txt", "content": "OK"},
                        intent="create artifact",
                        expected_observation="artifact exists",
                        if_fail_next="stop",
                    ),),
                evidence_gap="The next action must resolve the current evidence gap",
                )
            if self._step == 1:
                self._step += 1
                return SolverTurn(
                    kind="act",
                    summary="observe the written artifact",
                    actions=(ActionRequest(
                        action_id="read",
                        kind="read_file",
                        capability_id="filesystem",
                        arguments={"path": "out.txt"},
                        intent="observe current artifact state before submission",
                        expected_observation="out.txt contains OK",
                        if_fail_next="repair or report blocker",
                    ),),
                    evidence_gap="The written artifact has not yet been observed",
                )
            self._step += 1
            return SolverTurn(
                kind="submit_outcome",
                summary="submit",
                claim="out.txt contains OK",
                evidence_refs=(evidence_alias("step-1:read:read"),),
            )

        def verify(self, packet, compiled, ledger):
            self.verifier_packets.append(packet)
            return {"verdict": "blocked_by_tooling", "summary": "test verifier blocks"}

    hooks = Hooks()
    result = AetherNextKernel(max_steps=3).run(_env(), MemoryExecutor(workspace_root="/app"), hooks)
    assert result.status != "completed"
    assert hooks.verifier_packets
    dynamic = hooks.verifier_packets[0]["dynamic_state"]
    assert dynamic["runtime_facts"]["workspace_root"] == "/app"
    assert dynamic["files"]["out.txt"]["status"] == "modified"



def test_result_metrics_preserve_verifier_errors_from_immutable_receipts() -> None:
    result = KernelResult(
        status="incomplete",
        step=4,
        reconfigurations=0,
        receipts=(
            Receipt(
                "verifier-activation-1:parse-error-1", 2, "verifier_parse_error", False,
                "verifier provider/protocol attempt rejected",
                failure_class="verifier_protocol_error",
                payload={"error": "earlier verifier defect", "activation_ordinal": 1},
            ),
        ),
    )
    metrics = parse_protocol_metrics(result)
    assert metrics["verifier_parse_error_count"] == 1
    errors = model_parse_errors_for_row(result, hook_errors=[])
    assert len(errors) == 1
    assert errors[0]["kind"] == "verifier_parse_error"
    assert errors[0]["error"] == "earlier verifier defect"


def test_verifier_activation_error_custody_survives_later_clean_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}

    def fake_verify(hooks, packet, compiled, ledger, inspector):
        calls["count"] += 1
        hooks.last_parse_errors = (
            ["earlier verifier protocol defect"] if calls["count"] == 1 else []
        )
        return '{"verdict":"uncertain_missing_evidence"}'

    monkeypatch.setattr("aether.model_hooks._verify_with_inspector_impl", fake_verify)
    dummy = lambda *_args, **_kwargs: "{}"
    hooks = ModelHooks(dummy, dummy)
    ledger = ExecutionLedger()
    compiled = object()

    hooks.verify_with_inspector({}, compiled, ledger, object())
    hooks.verify_with_inspector({}, compiled, ledger, object())

    durable = [r for r in ledger.all_receipts() if r.kind == "verifier_parse_error"]
    assert len(durable) == 1
    assert durable[0].payload["error"] == "earlier verifier protocol defect"
    result = KernelResult(
        status="incomplete", step=0, reconfigurations=0,
        receipts=ledger.all_receipts(),
    )
    errors = model_parse_errors_for_row(result, hook_errors=hooks.last_parse_errors)
    assert [row["error"] for row in errors] == ["earlier verifier protocol defect"]
