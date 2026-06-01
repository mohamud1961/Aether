import json
from pathlib import Path

from blocks.execution import flat_loop
from blocks.tools import raw_bash
from blocks.verification import trust_model
from runner.agent import _apply_terminal_outcome_cleanup_order_guard
from runner.eval_batch_runner import _build_recommendation_draft, run_batch

PACKET04_CLOSEOUT_PATH = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_04_first_atomic_variants/synthesis/principal_closeout_decision.md"
)
PACKET04_BATCH_PLAN_PATH = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_04_first_atomic_variants/outputs/atomic_variant_batch_plan.md"
)
PACKET03_ACTIVE_CARDS_PATH = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_03_atomic_eval_families/outputs/eval_cards.active.jsonl"
)

ACTIVE_FIRST_SLICE_VARIANTS = (
    "v04_vc_01_layered_non_substitution_reason_codes",
    "v04_ex_01_single_terminal_outcome_cleanup_order_guard",
    "v04_tb_02_permission_runtime_attribution_split",
)
BOUNDED_FIRST_SLICE_VARIANTS = (
    "v04_ex_02_cwd_workdir_invariant_propagation_guard",
    "v04_cb_01_decoy_resistant_target_selection",
    "v04_tb_01_tool_call_contract_classifier",
)
DEFERRED_VARIANTS = (
    "v04_rb_01_interrupt_retry_spiral_breaker",
    "v04_vc_02_verifier_final_contradiction_arbiter",
    "v04_or_01_planner_orchestration_with_verifier_gate",
)


class _NoToolModel:
    def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        _ = messages, kwargs
        return {"text": "done", "tool_calls": [], "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}


class _Sandbox:
    def __init__(self, payload):
        self._payload = dict(payload)

    def exec(self, command):  # type: ignore[no-untyped-def]
        _ = command
        return dict(self._payload)


def _load_active_eval_cards() -> dict[str, dict]:
    cards = {}
    for line in PACKET03_ACTIVE_CARDS_PATH.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        cards[row["eval_id"]] = row
    return cards


def test_packet04_governance_closed_and_first_slice_roster_is_fixed():
    closeout_text = PACKET04_CLOSEOUT_PATH.read_text(encoding="utf-8")
    batch_plan_text = PACKET04_BATCH_PLAN_PATH.read_text(encoding="utf-8")

    assert "closed_ready_for_builder_prompt_pack" in closeout_text
    for variant_id in ACTIVE_FIRST_SLICE_VARIANTS:
        assert f"- `{variant_id}`" in closeout_text
        assert f"`{variant_id}`" in batch_plan_text
    for variant_id in BOUNDED_FIRST_SLICE_VARIANTS:
        assert f"- `{variant_id}`" in closeout_text
    for variant_id in DEFERRED_VARIANTS:
        assert f"- `{variant_id}`" in closeout_text

    assert "sc_b_01" in closeout_text
    assert "measured baseline only; not promotable" in batch_plan_text


def test_v04_vc_01_layered_non_substitution_reason_codes_are_wired_in_trust_model():
    workspace_state = {
        "model_claimed_done": True,
        "layer_statuses": {
            "L0_inline_assertion": "pass",
            "L1_verifier_artifact": "fail",
            "L2_replay_or_state_grader": "pass",
            "L4_final_acceptance": "pass",
        },
    }

    verified = trust_model.check("task", workspace_state)

    assert verified is False
    assert "layered_acceptance_rejected" in workspace_state["verification_reason_codes"]
    assert (
        "non_substitution_violation_l4_over_l1_verifier_artifact"
        in workspace_state["verification_substitution_violations"]
    )
    assert workspace_state["verification_layer_statuses"]["L1_verifier_artifact"] == "fail"


def test_v04_ex_01_flat_loop_exports_single_terminal_outcome_and_cleanup_order():
    result = flat_loop.run_loop(
        model=_NoToolModel(),
        tools={},
        context={"history": [{"role": "user", "content": "hi"}], "manage_history": lambda h, o: h + [o]},
        max_steps=2,
    )

    assert result["status"] == "completed"
    assert result["terminal_write_count"] == 1
    assert result["terminal_outcome"]["status"] == "completed"
    assert "loop_cleanup_completed" in result["cleanup_completion_reason_codes"]
    assert result["unresolved_state_exit_count"] == 0
    lifecycle_events = result["lifecycle_sequence_fingerprint"].split(">")
    assert lifecycle_events.index("terminal_outcome_written") < lifecycle_events.index("cleanup_started")


def test_v04_ex_01_runner_guard_downgrades_terminal_status_when_interrupt_cleanup_missing():
    execution_result = {
        "status": "completed",
        "terminal_outcome": {"status": "completed", "reason_code": "no_tool_calls", "step": 0},
        "terminal_write_count": 1,
        "cleanup_completion_reason_codes": [],
        "runtime_probe": {"interrupt_observed": True, "cleanup_observed": False},
        "lifecycle_sequence_fingerprint": "loop_entered>terminal_outcome_written>cleanup_started>cleanup_completed",
    }

    final_status = _apply_terminal_outcome_cleanup_order_guard(
        execution_result=execution_result,
        recovery_action=None,
    )

    assert final_status == "error"
    assert execution_result["status"] == "error"
    assert execution_result["terminal_outcome"]["status"] == "error"
    assert "runtime_probe_cleanup_missing" in execution_result["cleanup_completion_reason_codes"]
    assert execution_result["unresolved_state_exit_count"] == 1


def test_v04_tb_02_permission_runtime_attribution_split_marks_permission_and_runtime_separately():
    permission_result = raw_bash.execute_tool_call(
        {"name": "raw_bash", "arguments": {"command": "cat /root/secret"}},
        _Sandbox({"exit_code": 126, "stdout": "", "stderr": "Permission denied", "timed_out": False}),
    )
    runtime_result = raw_bash.execute_tool_call(
        {"name": "raw_bash", "arguments": {"command": "cat missing.txt"}},
        _Sandbox({"exit_code": 1, "stdout": "", "stderr": "No such file or directory", "timed_out": False}),
    )

    assert permission_result["result_class"] == "permission_denied"
    assert permission_result["reason_code"] == "tool_permission_denied"
    assert permission_result["permission_denied"] is True
    assert permission_result["runtime_error"] is False

    assert runtime_result["result_class"] == "runtime_error"
    assert runtime_result["reason_code"] == "tool_runtime_nonzero_exit"
    assert runtime_result["permission_denied"] is False
    assert runtime_result["runtime_error"] is True


def test_packet04_recommendation_fence_keeps_sc_b_01_comparator_only():
    recommendation = _build_recommendation_draft(
        {
            "batch_id": "packet04-atomic-reference",
            "eval_family": "packet_04_atomic_reference_deterministic",
            "task_set_id": "packet04-reference-set",
            "variant_ids": ["sc_b_01", ACTIVE_FIRST_SLICE_VARIANTS[0]],
            "fixed_invariants": {"comparator_variant_id": "sc_b_01"},
        },
        [
            {
                "variant_id": "sc_b_01",
                "run_id": "run-001",
                "score_summary": {"final_verdict": "pass"},
                "budget_used": {"estimated_tokens": 8},
            },
            {
                "variant_id": ACTIVE_FIRST_SLICE_VARIANTS[0],
                "run_id": "run-002",
                "score_summary": {"final_verdict": "pass"},
                "budget_used": {"estimated_tokens": 9},
            },
        ],
    )

    by_variant = {candidate["variant_id"]: candidate for candidate in recommendation["candidate_actions"]}
    assert by_variant["sc_b_01"]["proposed_status"] == "bound"
    assert "cannot self-promote" in by_variant["sc_b_01"]["rationale"]
    assert by_variant[ACTIVE_FIRST_SLICE_VARIANTS[0]]["proposed_status"] == "hold_for_more_evidence"
    assert "Mandatory governance evidence is incomplete or non-promotable under Packet 04A" in by_variant[
        ACTIVE_FIRST_SLICE_VARIANTS[0]
    ]["rationale"]


def test_packet04_active_variant_id_runs_on_accepted_packet03_eval_surface_without_eval_mutation(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_completion_layer_contract_guard"
    batch_spec = {
        "batch_id": "packet04-local-wire-check",
        "packet_stage": "packet_04",
        "eval_family": "packet_04_first_atomic_variants",
        "eval_ids": [eval_id],
        "variant_ids": [ACTIVE_FIRST_SLICE_VARIANTS[0]],
        "task_set_id": "packet04-local-task-set",
        "task_tier": "atomic",
        "rerun_count": 1,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "provider_route": "local_stub",
        "fixed_invariants": {"comparator_variant_id": "sc_b_01", "packet": "packet_04"},
        "budget_caps": {"run_count": 1, "tokens": 1000, "usd": 1.0},
        "stability_budget_caps": {"run_count": 1, "tokens": 1000, "usd": 1.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "guardrail_debug",
        "promotion_authority": False,
        "execution_mode_lock": {eval_id: "deterministic_no_model"},
        "eval_card_refs": {eval_id: f"inline:{eval_id}"},
        "task_cases": [{"task_id": "task-001", "task_prompt": "packet04 local verification"}],
    }

    result = run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: eval_cards[eval_id]},
    )

    assert result["run_count"] == 1
    recommendations = json.loads(
        Path(result["recommendations_path"]).read_text(encoding="utf-8")
    )["candidate_actions"]
    assert recommendations[0]["variant_id"] == ACTIVE_FIRST_SLICE_VARIANTS[0]
