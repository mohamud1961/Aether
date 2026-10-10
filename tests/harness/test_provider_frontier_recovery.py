from __future__ import annotations

import json

import pytest

from aether.execution import MemoryExecutor
from aether.harbor_runtime import (
    P4_CONTROL_ARM,
    P4_NO_TOOL_MAX_OUTPUT_ARM,
    P4_PROVIDER_FRONTIER_RECOVERY_ARM_ENV,
    build_selected_frontier_models,
    selected_p4_provider_frontier_recovery_mode,
)
from aether.kernel import AetherNextKernel
from aether.model_hooks import ModelProviderError
from aether.provider_frontier_recovery import (
    CONTROL,
    NO_TOOL_MAX_OUTPUT_V1,
    ProviderFrontierReserveReached,
    classify_frontier_recovery,
    protected_final_reserve_s,
)
from aether.providers.responses_websocket import ResponsesWebSocketError
from aether.providers import azure_model as azure_model_module
from aether.providers.azure_model import AzureModelCallable, AzureModelError, is_retryable_azure_error
from aether.runtime_ir import ActionRequest, SolverTurn
from tests.harness.test_prompt_cache_stability import _env


def _no_tool_max_output_error(*, role: str = "solver", native_tool: bool = False) -> ModelProviderError:
    cause = ResponsesWebSocketError(
        "unit incomplete",
        terminal=True,
        retry_safe=False,
        event_type="response.incomplete",
        response_id="resp-unit",
        request_accepted=True,
        partial_output_observed=True,
        native_tool_call_observed=native_tool,
        incomplete_reason="max_output_tokens",
        replay_safety_reason="provider_incomplete_response_not_replay_safe",
        acceptance_known=True,
    )
    return ModelProviderError(cause, role=role)


def test_classification_requires_explicit_accepted_no_tool_max_output_boundary() -> None:
    exc = _no_tool_max_output_error()
    decision = classify_frontier_recovery(
        exc, mode=NO_TOOL_MAX_OUTPUT_V1, used_recoveries=0,
    )
    assert decision.eligible is True
    assert decision.reason == "accepted_no_tool_max_output_incomplete"
    assert decision.facts["request_accepted"] is True
    assert decision.facts["partial_output_observed"] is True
    assert decision.facts["native_tool_call_observed"] is False
    assert decision.facts["native_tool_call_observed_known"] is True


def test_classification_fails_closed_for_control_native_tool_or_unknown_transport() -> None:
    assert classify_frontier_recovery(
        _no_tool_max_output_error(), mode=CONTROL, used_recoveries=0,
    ).eligible is False

    native = classify_frontier_recovery(
        _no_tool_max_output_error(native_tool=True),
        mode=NO_TOOL_MAX_OUTPUT_V1,
        used_recoveries=0,
    )
    assert native.eligible is False
    assert native.reason == "native_tool_observed"

    unknown = ModelProviderError(RuntimeError("opaque provider failure"), role="solver")
    decision = classify_frontier_recovery(
        unknown, mode=NO_TOOL_MAX_OUTPUT_V1, used_recoveries=0,
    )
    assert decision.eligible is False
    assert decision.reason in {
        "not_response_incomplete",
        "not_supported_no_tool_boundary",
        "native_tool_observation_unknown",
    }


def test_classification_never_recovers_verifier_or_second_failure() -> None:
    verifier = classify_frontier_recovery(
        _no_tool_max_output_error(role="verifier"),
        mode=NO_TOOL_MAX_OUTPUT_V1,
        used_recoveries=0,
    )
    assert verifier.eligible is False
    assert verifier.reason == "non_solver_role"

    exhausted = classify_frontier_recovery(
        _no_tool_max_output_error(),
        mode=NO_TOOL_MAX_OUTPUT_V1,
        used_recoveries=1,
    )
    assert exhausted.eligible is False
    assert exhausted.reason == "recovery_budget_exhausted"


class _RecoveringHooks:
    def __init__(self, *, always_fail: bool = False) -> None:
        self.solve_calls = 0
        self.reset_calls = 0
        self.always_fail = always_fail
        self.context_packets: list[dict] = []

    def reset_solver_continuity_for_recovery(self) -> bool:
        self.reset_calls += 1
        return True

    def solve(self, messages, compiled):
        self.solve_calls += 1
        packet = json.loads(messages[-1]["content"].split("\n", 1)[1])
        self.context_packets.append(packet)
        if self.always_fail or self.solve_calls == 1:
            raise _no_tool_max_output_error()
        return SolverTurn(
            kind="act",
            summary="continue from authoritative task state",
            actions=(ActionRequest(
                action_id="write-after-recovery",
                kind="write_file",
                capability_id="filesystem",
                arguments={"path": "out.txt", "content": "OK"},
                intent="perform the next model-chosen task action",
                expected_observation="out.txt is written",
                if_fail_next="report the observed failure",
            ),),
            evidence_gap="The requested artifact is still absent",
        )


def test_kernel_default_control_still_terminates_provider_failure() -> None:
    hooks = _RecoveringHooks()
    result = AetherNextKernel(max_steps=3).run(
        _env(), MemoryExecutor(workspace_root="/app"), hooks,
    )
    assert result.status == "provider_failure"
    assert hooks.solve_calls == 1
    assert hooks.reset_calls == 0
    assert not any(r.kind == "provider_frontier_recovery_admission" for r in result.receipts)


def test_kernel_control_failure_preserves_counterfactual_frontier_facts_without_recovery() -> None:
    hooks = _RecoveringHooks()
    result = AetherNextKernel(max_steps=3).run(
        _env(), MemoryExecutor(workspace_root="/app"), hooks,
    )

    assert result.status == "provider_failure"
    failure = next(r for r in result.receipts if r.kind == "provider_failure")
    observed = failure.payload["provider_frontier_counterfactual"]
    assert observed["mode"] == NO_TOOL_MAX_OUTPUT_V1
    assert observed["eligible"] is True
    assert observed["reason"] == "accepted_no_tool_max_output_incomplete"
    assert observed["behavior_changed"] is False
    assert observed["facts"]["request_accepted"] is True
    assert observed["facts"]["partial_output_observed"] is True
    assert observed["facts"]["native_tool_call_observed"] is False
    assert hooks.solve_calls == 1
    assert hooks.reset_calls == 0
    assert not any(r.kind == "provider_frontier_recovery_admission" for r in result.receipts)


def test_second_treatment_failure_records_counterfactual_budget_exhausted() -> None:
    hooks = _RecoveringHooks(always_fail=True)
    result = AetherNextKernel(
        max_steps=4,
        provider_frontier_recovery_mode=NO_TOOL_MAX_OUTPUT_V1,
    ).run(_env(), MemoryExecutor(workspace_root="/app"), hooks)

    assert result.status == "provider_failure"
    terminal_failure = [r for r in result.receipts if r.kind == "provider_failure"][-1]
    observed = terminal_failure.payload["provider_frontier_counterfactual"]
    assert observed["eligible"] is False
    assert observed["reason"] == "recovery_budget_exhausted"
    assert observed["facts"]["used_recoveries"] == 1
    assert observed["behavior_changed"] is False


def test_kernel_treatment_records_failure_resets_continuity_and_gives_frontier_one_fresh_turn() -> None:
    hooks = _RecoveringHooks()
    executor = MemoryExecutor(workspace_root="/app")
    result = AetherNextKernel(
        max_steps=2,
        provider_frontier_recovery_mode=NO_TOOL_MAX_OUTPUT_V1,
    ).run(_env(), executor, hooks)

    assert result.status != "provider_failure"
    assert hooks.solve_calls == 2
    assert hooks.reset_calls == 1
    failure = next(r for r in result.receipts if r.kind == "provider_frontier_failure")
    admission = next(
        r for r in result.receipts if r.kind == "provider_frontier_recovery_admission"
    )
    assert failure.success is False
    assert failure.failure_class == "provider_output_incomplete_no_tool"
    assert failure.payload["native_tool_call_observed"] is False
    assert admission.payload["provider_response_replayed"] is False
    assert admission.payload["task_state_mutated_by_recovery"] is False

    assert len(hooks.context_packets) == 2
    facts = hooks.context_packets[1].get("unresolved_runtime_facts", [])
    assert any(
        row.get("failure_class") == "provider_output_incomplete_no_tool"
        for row in facts
    )


def test_kernel_treatment_is_one_shot_and_second_eligible_failure_terminates() -> None:
    hooks = _RecoveringHooks(always_fail=True)
    result = AetherNextKernel(
        max_steps=4,
        provider_frontier_recovery_mode=NO_TOOL_MAX_OUTPUT_V1,
    ).run(_env(), MemoryExecutor(workspace_root="/app"), hooks)

    assert result.status == "provider_failure"
    assert hooks.solve_calls == 2
    assert hooks.reset_calls == 1
    assert sum(
        r.kind == "provider_frontier_recovery_admission" for r in result.receipts
    ) == 1


def test_invalid_provider_frontier_recovery_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="provider frontier recovery mode"):
        AetherNextKernel(provider_frontier_recovery_mode="invent_strategy")


def test_harbor_p4_selector_is_default_off_and_production_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(P4_PROVIDER_FRONTIER_RECOVERY_ARM_ENV, raising=False)
    assert selected_p4_provider_frontier_recovery_mode(build_selected_frontier_models) == P4_CONTROL_ARM

    monkeypatch.setenv(P4_PROVIDER_FRONTIER_RECOVERY_ARM_ENV, P4_NO_TOOL_MAX_OUTPUT_ARM)
    assert (
        selected_p4_provider_frontier_recovery_mode(build_selected_frontier_models)
        == P4_NO_TOOL_MAX_OUTPUT_ARM
    )
    assert selected_p4_provider_frontier_recovery_mode(object()) == P4_CONTROL_ARM


def test_harbor_p4_selector_rejects_unknown_production_arm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(P4_PROVIDER_FRONTIER_RECOVERY_ARM_ENV, "invent_strategy")
    with pytest.raises(RuntimeError, match="AETHER_RESEARCH_P4_PROVIDER_FRONTIER_RECOVERY"):
        selected_p4_provider_frontier_recovery_mode(build_selected_frontier_models)


def test_protected_final_reserve_is_bounded_by_corpus_max_and_task_fraction() -> None:
    assert protected_final_reserve_s(None) is None
    assert protected_final_reserve_s(0) is None
    assert protected_final_reserve_s(420) == pytest.approx(105.0)
    assert protected_final_reserve_s(900) == pytest.approx(120.0)
    assert protected_final_reserve_s(1800) == pytest.approx(120.0)
    assert protected_final_reserve_s(120) == pytest.approx(30.0)


def test_reserve_boundary_is_eligible_only_with_explicit_no_tool_transport_facts() -> None:
    cause = ProviderFrontierReserveReached(
        request_accepted=True,
        partial_output_observed=True,
        native_tool_call_observed=False,
        remaining_run_s=119.5,
        protected_reserve_s=120.0,
    )
    exc = ModelProviderError(cause, role="solver")
    decision = classify_frontier_recovery(
        exc, mode=NO_TOOL_MAX_OUTPUT_V1, used_recoveries=0,
    )
    assert decision.eligible is True
    assert decision.reason == "accepted_no_tool_protected_final_reserve"
    assert decision.facts["remaining_run_s_at_frontier_stop"] == pytest.approx(119.5)
    assert decision.facts["protected_reserve_s"] == pytest.approx(120.0)
    assert decision.facts["replay_safety_reason"] == "accepted_partial_provider_response_not_replayed"


def test_protected_reserve_interrupt_is_one_shot_so_recovery_can_use_reserve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = AzureModelCallable.__new__(AzureModelCallable)
    model._role = "solver"
    model._provider_frontier_recovery_mode = NO_TOOL_MAX_OUTPUT_V1
    model._provider_frontier_protected_reserve_s = 120.0
    model._provider_frontier_reserve_consumed = False
    monkeypatch.setattr(azure_model_module, "remaining_run_s", lambda: 119.0)
    facts = {
        "request_accepted": True,
        "partial_output_observed": True,
        "native_tool_call_observed": False,
    }
    with pytest.raises(ProviderFrontierReserveReached):
        model._provider_frontier_inflight_guard(facts)
    assert model._provider_frontier_reserve_consumed is True

    # The single fresh recovery call runs inside the protected reserve. It must
    # not be killed on its first reasoning item; the hard task deadline remains
    # the outer bound and the kernel still allows only one recovery admission.
    model._provider_frontier_inflight_guard(facts)


def test_provider_frontier_reconfiguration_resets_one_shot_reserve_state() -> None:
    model = AzureModelCallable.__new__(AzureModelCallable)
    model._role = "solver"
    model._provider_frontier_recovery_mode = NO_TOOL_MAX_OUTPUT_V1
    model._provider_frontier_protected_reserve_s = 120.0
    model._provider_frontier_reserve_consumed = True
    model.configure_provider_frontier_recovery(
        NO_TOOL_MAX_OUTPUT_V1, protected_reserve_s=105.0
    )
    assert model._provider_frontier_reserve_consumed is False
    assert model._provider_frontier_protected_reserve_s == pytest.approx(105.0)


def test_protected_reserve_interrupt_is_never_provider_retryable() -> None:
    cause = ProviderFrontierReserveReached(
        request_accepted=True,
        partial_output_observed=True,
        native_tool_call_observed=False,
        remaining_run_s=119.0,
        protected_reserve_s=120.0,
    )
    try:
        raise AzureModelError(f"responses native-tool call failed: {cause}") from cause
    except AzureModelError as exc:
        assert is_retryable_azure_error(exc) is False
