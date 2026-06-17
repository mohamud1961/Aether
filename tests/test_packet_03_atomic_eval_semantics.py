import json
from pathlib import Path

import pytest

from blocks.context import full_history
from blocks.execution import flat_loop
from runner.eval_batch_runner import (
    _build_recommendation_draft,
    _resolve_batch_model_route_override,
    _token_and_cost_summary,
    run_batch,
)
from runner.experiment_contracts import validate_trace_summary
from runner.evaluator import build_score_envelope
from runner.packet03_eval_fixtures import get_packet03_eval_lane_policy, materialize_packet03_eval_fixture
from runner.packet03_eval_graders import apply_packet03_eval_grader
from runner.packet04_route_manifest import baseline_execution_run_loop
from runner.model_client import LocalStubModelClient
from runner.schemas import (
    SUCCESSOR_RHV1_OBSERVED_MARKER_IDS,
    SchemaValidationError,
    default_layers,
)


ACTIVE_CARDS_PATH = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_03_atomic_eval_families/outputs/eval_cards.active.jsonl"
)


class _CapturingModel:
    def __init__(self):
        self.kwargs = None

    def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        self.kwargs = dict(kwargs)
        return {
            "text": "done",
            "tool_calls": [],
            "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18, "usd": 0.01},
        }


class _ActivationContractRetryModel:
    def __init__(self):
        self.calls = 0

    def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        _ = messages
        _ = kwargs
        self.calls += 1
        if self.calls == 1:
            return {
                "text": "I will do that now.",
                "tool_calls": [],
                "usage": {"input_tokens": 7, "output_tokens": 6, "total_tokens": 13, "usd": 0.01},
            }
        return {
            "text": "",
            "tool_calls": [{"name": "raw_bash", "arguments": {"command": "echo packet03_activation_retry"}}],
            "usage": {"input_tokens": 4, "output_tokens": 4, "total_tokens": 8, "usd": 0.01},
        }


class _ActivationContractRetryHistoryModel:
    def __init__(self):
        self.calls = 0
        self.messages_by_call: list[list[dict[str, object]]] = []

    def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        self.calls += 1
        self.messages_by_call.append([dict(message) for message in messages if isinstance(message, dict)])
        if self.calls == 1:
            return {
                "text": "draft no-tool response",
                "tool_calls": [],
                "usage": {"input_tokens": 8, "output_tokens": 5, "total_tokens": 13, "usd": 0.01},
            }
        return {
            "text": "",
            "tool_calls": [{"name": "raw_bash", "arguments": {"command": "cat workspace/a/payload.txt"}}],
            "usage": {"input_tokens": 4, "output_tokens": 4, "total_tokens": 8, "usd": 0.01},
        }


def _load_active_eval_cards() -> dict[str, dict]:
    cards = {}
    for line in ACTIVE_CARDS_PATH.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        cards[row["eval_id"]] = row
    return cards


def _single_eval_batch_spec(*, tmp_path, batch_id, eval_id, execution_mode, rerun_count=1):
    return {
        "batch_id": batch_id,
        "packet_stage": "packet_03",
        "eval_family": "packet_03_semantic_test",
        "eval_ids": [eval_id],
        "variant_ids": ["sc_b_01"],
        "task_set_id": "packet03-semantic-test-set",
        "task_tier": "atomic",
        "rerun_count": rerun_count,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "provider_route": "local_stub",
        "fixed_invariants": {
            "comparator_variant_id": "sc_b_01",
            "evaluation_lane": "stability_lane",
            "packet": "packet_03",
        },
        "budget_caps": {"run_count": rerun_count, "tokens": 1000, "usd": 1.0},
        "stability_budget_caps": {"run_count": rerun_count, "tokens": 1000, "usd": 1.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "stability_lane",
        "execution_mode_lock": {eval_id: execution_mode},
        "eval_card_refs": {eval_id: f"inline:{eval_id}"},
        "task_cases": [{"task_id": "task-001", "task_prompt": "semantic probe"}],
    }


def _successor_smoke_batch_spec(*, tmp_path, batch_id: str) -> dict:
    return {
        "batch_id": batch_id,
        "packet_stage": "packet_06",
        "packet04_route_scope": "successor_slice1_compile",
        "eval_family": "packet_04_first_atomic_variants",
        "eval_ids": [
            "ae_internal_discovery_evidence_efficiency_v1",
            "ae_internal_multifile_repair_test_verify_v1",
        ],
        "variant_ids": ["spb_01", "rhv1_ref_01"],
        "task_set_id": "successor_smoke_first_bounded_live_gate_set",
        "task_tier": "project_owned_tb_style",
        "rerun_count": 1,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "model_tier_selector": "screening_default",
        "provider_route": "local_stub",
        "fixed_invariants": {
            "comparator_variant_id": "spb_01",
            "legacy_visibility_comparator_variant_id": "sc_b_01",
            "packet04_route_scope": "successor_slice1_compile",
            "primary_comparator_variant_id": "spb_01",
        },
        "budget_caps": {"run_count": 4, "tokens": 20000, "usd": 2.0},
        "stability_budget_caps": {"run_count": 4, "tokens": 20000, "usd": 2.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "promotion",
        "promotion_authority": True,
        "execution_mode_lock": {
            "ae_internal_discovery_evidence_efficiency_v1": "multistep_batchable",
            "ae_internal_multifile_repair_test_verify_v1": "multistep_batchable",
        },
        "eval_card_refs": {
            "ae_internal_discovery_evidence_efficiency_v1": "inline:ae_internal_discovery_evidence_efficiency_v1",
            "ae_internal_multifile_repair_test_verify_v1": "inline:ae_internal_multifile_repair_test_verify_v1",
        },
        "lane_blocker_policy": "packet04a_lane_blocker_policy.v1",
        "route_contract_id": "packet04_route_manifest.v1",
        "ownership_bucket_map_ref": "runner/packet04_route_manifest.py",
        "variant_card_refs": {
            "spb_01": "tracking/collab/stage_03_execution_planning/packets/packet_04_first_atomic_variants/outputs/variant_cards.md#variant_id=spb_01",
            "rhv1_ref_01": "tracking/collab/stage_03_execution_planning/packets/packet_04_first_atomic_variants/outputs/variant_cards.md#variant_id=rhv1_ref_01",
        },
        "task_cases": [
            {
                "task_id": "successor_smoke_gate_t1",
                "task_prompt": "Operate as a bounded smoke gate for the successor reference harness.",
                "claim_route_id": "cr_successor_smoke_first_live_gate",
                "task_intent": "successor_smoke_infrastructure_truth_gate",
            }
        ],
    }


def _result_records(batch_dir: Path) -> list[dict]:
    result_path = batch_dir / "result_records.jsonl"
    return [
        json.loads(line)
        for line in result_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _score_envelope_for_record(batch_dir: Path, record: dict) -> dict:
    score_ref = record["run_artifact_refs"]["score_envelope_ref"]
    return json.loads((batch_dir / score_ref).read_text(encoding="utf-8"))


def _trace_summaries(batch_dir: Path) -> list[dict]:
    trace_path = batch_dir / "trace_summaries.jsonl"
    return [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _seed_execution_result(eval_id: str) -> dict:
    layers = default_layers()
    layers["L1_verifier_artifact"]["status"] = "pass"
    layers["L1_verifier_artifact"]["score"] = {"kind": "boolean", "value": True}
    layers["L1_verifier_artifact"]["artifact_ref"] = "inline:test_events"
    layers["L4_final_acceptance"]["status"] = "fail"
    layers["L4_final_acceptance"]["score"] = {"kind": "boolean", "value": False}
    score = build_score_envelope(
        run_id=f"test-run-{eval_id}",
        benchmark_id="packet03_semantics",
        case_id=eval_id,
        layers=layers,
        final_verdict="fail",
    )
    return {
        "score_envelope": score,
        "execution": {
            "status": "completed",
            "history": [],
            "steps": [],
            "step_count": 0,
            "terminal_write_count": 1,
            "cleanup_completion_reason_codes": ["loop_cleanup_completed"],
            "lifecycle_sequence_fingerprint": "loop_entered>terminal_outcome_written>cleanup_started>cleanup_completed>loop_exited",
            "unresolved_state_exit_count": 0,
            "cleanup_completed": True,
            "cleanup_race_detected": False,
            "post_cancel_tool_return_count": 0,
            "lifecycle_reason_codes": [],
        },
        "run_events": [],
        "verification": {
            "verified": True,
            "reason_codes": [],
            "substitution_violations": [],
            "layer_statuses": {
                "L0_inline_assertion": "pass",
                "L1_verifier_artifact": "pass",
                "L2_replay_or_state_grader": "pass",
                "L4_final_acceptance": "pass",
            },
        },
        "verified": False,
    }


def _verification_v2_eval_card() -> dict:
    return {
        "eval_id": "ae_verification_reason_code_quality_v2",
        "family_id": "af_completion_verification_layering",
        "block_family": "VerificationBlock",
        "mechanism_claim": "Require exact verification reason-code and substitution-violation quality under non-substitution pressure.",
        "target_failure": "completion_false_positive",
        "fixed_invariants": {
            "provider_route": "none",
            "settings_fingerprint": "deterministic_verification_quality_v2",
            "grader_version": "p05a_verification_reason_code_quality_grader_v2",
            "fixture_version": "p05a_verification_reason_code_quality_v2",
            "comparator_variant_id": "reference_baseline_packet_02",
        },
        "execution_mode": "deterministic_no_model",
        "batch_eligibility": True,
        "model_tier_policy": {
            "screening_default": "no_model",
            "screening_fallback": "not_applicable",
            "promotion_tier": "not_applicable",
        },
        "score_layer_expectations": {
            "l0_inline_assertion": "required",
            "l1_verifier_artifact": "required",
            "l2_replay_or_state_grader": "required",
            "l3_llm_judge": "not_applicable",
            "l4_final_acceptance_reward": "required",
            "non_substitution_rule": "required",
        },
        "human_gate_required": True,
    }


def _lifecycle_v2_eval_card() -> dict:
    return {
        "eval_id": "ae_lifecycle_adversarial_terminality_v2",
        "family_id": "af_execution_lifecycle_integrity",
        "block_family": "ExecutionBlock",
        "mechanism_claim": "Require explicit lifecycle anomaly detection under adversarial terminality and cleanup pressure.",
        "target_failure": "process_lifecycle_and_cancellation_boundary_failure",
        "fixed_invariants": {
            "provider_route": "none",
            "settings_fingerprint": "deterministic_lifecycle_adversarial_v2",
            "grader_version": "p05a_lifecycle_adversarial_terminality_grader_v2",
            "fixture_version": "p05a_lifecycle_adversarial_terminality_v2",
            "comparator_variant_id": "reference_baseline_packet_02",
        },
        "execution_mode": "deterministic_no_model",
        "batch_eligibility": True,
        "evaluation_lane": "promotion",
        "model_tier_policy": {
            "screening_default": "no_model",
            "screening_fallback": "not_applicable",
            "promotion_tier": "not_applicable",
        },
        "score_layer_expectations": {
            "l0_inline_assertion": "required",
            "l1_verifier_artifact": "required",
            "l2_replay_or_state_grader": "required",
            "l3_llm_judge": "not_applicable",
            "l4_final_acceptance_reward": "required",
            "non_substitution_rule": "required",
        },
        "human_gate_required": True,
    }


def _workspace_target_decoy_generalization_v2_eval_card() -> dict:
    return {
        "eval_id": "ae_workspace_target_decoy_generalization_v2",
        "family_id": "af_workspace_path_target_integrity",
        "block_family": "ContextBlock",
        "mechanism_claim": "Require explicit target/decoy evidence under rotated decoy regimes with development-transfer framing.",
        "target_failure": "workspace_target_miss",
        "fixed_invariants": {
            "provider_route": "oauth",
            "settings_fingerprint": "p05a_workspace_target_decoy_generalization_v2",
            "grader_version": "p05a_workspace_target_decoy_generalization_grader_v2",
            "fixture_version": "p05a_workspace_target_decoy_generalization_v2",
            "comparator_variant_id": "reference_baseline_packet_02",
        },
        "execution_mode": "one_shot_batchable",
        "batch_eligibility": True,
        "evaluation_lane": "guardrail_debug",
        "model_tier_policy": {
            "screening_default": "oauth:gpt-5.4-nano",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "score_layer_expectations": {
            "l0_inline_assertion": "required",
            "l1_verifier_artifact": "required",
            "l2_replay_or_state_grader": "required",
            "l3_llm_judge": "not_applicable",
            "l4_final_acceptance_reward": "required",
            "non_substitution_rule": "required",
        },
        "human_gate_required": True,
    }


def _workspace_target_decoy_multistep_v1_eval_card() -> dict:
    return {
        "eval_id": "ae_workspace_target_decoy_generalization_multistep_v1",
        "family_id": "af_workspace_path_target_integrity",
        "block_family": "ContextBlock",
        "mechanism_claim": "Require honest multistep target-vs-decoy grounding with first-turn observation and post-observation edit evidence.",
        "target_failure": "workspace_target_miss",
        "fixed_invariants": {
            "provider_route": "oauth",
            "settings_fingerprint": "p05a_workspace_target_multistep_v1",
            "grader_version": "p05a_workspace_target_multistep_grader_v1",
            "fixture_version": "p05a_workspace_target_multistep_v1",
            "comparator_variant_id": "reference_baseline_packet_02",
        },
        "execution_mode": "multistep_batchable",
        "multistep_turn_budget": 3,
        "batch_eligibility": True,
        "evaluation_lane": "guardrail_debug",
        "model_tier_policy": {
            "screening_default": "oauth:gpt-5.4-nano",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "score_layer_expectations": {
            "l0_inline_assertion": "required",
            "l1_verifier_artifact": "required",
            "l2_replay_or_state_grader": "required",
            "l3_llm_judge": "not_applicable",
            "l4_final_acceptance_reward": "required",
            "non_substitution_rule": "required",
        },
        "human_gate_required": True,
    }


def _internal_toolchain_dependency_pressure_eval_card() -> dict:
    return {
        "eval_id": "ae_internal_toolchain_dependency_pressure_v1",
        "family_id": "af_tool_gateway_argument_result_contract",
        "block_family": "ToolBlock",
        "mechanism_claim": "Require strict tool-call contract handling under task-shaped toolchain/dependency pressure.",
        "target_failure": "tool_invocation_error",
        "fixed_invariants": {
            "provider_route": "oauth",
            "settings_fingerprint": "p06_toolchain_dependency_pressure_v1",
            "grader_version": "p06_toolchain_dependency_pressure_grader_v1",
            "fixture_version": "p06_toolchain_dependency_pressure_fixture_v1",
            "comparator_variant_id": "sc_b_01",
        },
        "execution_mode": "multistep_batchable",
        "batch_eligibility": True,
        "evaluation_lane": "promotion",
        "model_tier_policy": {
            "screening_default": "oauth:gpt-5.4-nano",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "score_layer_expectations": {
            "l0_inline_assertion": "required",
            "l1_verifier_artifact": "required",
            "l2_replay_or_state_grader": "required",
            "l3_llm_judge": "not_applicable",
            "l4_final_acceptance_reward": "required",
            "non_substitution_rule": "required",
        },
        "human_gate_required": True,
    }


def _internal_artifact_log_extraction_eval_card() -> dict:
    return {
        "eval_id": "ae_internal_artifact_log_extraction_v1",
        "family_id": "af_tool_gateway_argument_result_contract",
        "block_family": "ToolBlock",
        "mechanism_claim": "Require explicit permission-vs-runtime attribution evidence under artifact/log extraction pressure.",
        "target_failure": "permission_policy_runtime_mismatch",
        "fixed_invariants": {
            "provider_route": "oauth",
            "settings_fingerprint": "p06_artifact_log_extraction_v1",
            "grader_version": "p06_artifact_log_extraction_grader_v1",
            "fixture_version": "p06_artifact_log_extraction_fixture_v1",
            "comparator_variant_id": "sc_b_01",
        },
        "execution_mode": "multistep_batchable",
        "batch_eligibility": True,
        "evaluation_lane": "promotion",
        "model_tier_policy": {
            "screening_default": "oauth:gpt-5.4-nano",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "score_layer_expectations": {
            "l0_inline_assertion": "required",
            "l1_verifier_artifact": "required",
            "l2_replay_or_state_grader": "required",
            "l3_llm_judge": "not_applicable",
            "l4_final_acceptance_reward": "required",
            "non_substitution_rule": "required",
        },
        "human_gate_required": True,
    }


def test_flat_loop_forwards_tool_definitions_and_preserves_completion_usage():
    model = _CapturingModel()
    result = flat_loop.run_loop(
        model=model,
        tools={},
        context={"history": [{"role": "user", "content": "hi"}], "manage_history": full_history.manage},
        max_steps=1,
        tool_definitions=[{"name": "raw_bash"}],
    )

    assert model.kwargs == {"tools": [{"name": "raw_bash"}]}
    assert result["steps"][0]["completion"]["usage"]["total_tokens"] == 18


def test_workspace_target_activation_contract_retries_after_first_no_tool_completion(tmp_path):
    fixture_path = tmp_path / "packet03_fixture.json"
    fixture_path.write_text(
        json.dumps(
            {
                "exercise_activation_contract": {
                    "require_live_tool_call": True,
                    "preferred_tool_name": "raw_bash",
                    "first_turn_tool_only_response": True,
                }
            }
        ),
        encoding="utf-8",
    )
    model = _ActivationContractRetryModel()

    result = baseline_execution_run_loop(
        model=model,
        tools={
            "raw_bash": lambda call: {
                "tool_name": "raw_bash",
                "command": call["arguments"]["command"],
                "exit_code": 0,
                "stdout": "ok\n",
                "stderr": "",
                "timed_out": False,
            }
        },
        context={
            "history": [{"role": "user", "content": "workspace target activation"}],
            "manage_history": full_history.manage,
            "env_info": {"cwd": str(tmp_path), "task_id": "workspace_target_regime_alpha"},
        },
        max_steps=1,
        tool_definitions=[{"name": "raw_bash"}],
    )

    assert model.calls == 2
    assert result["step_count"] == 2
    assert result["steps"][0]["status"] == "activation_contract_retry_due_to_no_tool_calls"
    assert result["steps"][1]["tool_calls"] == 1


def test_workspace_target_multistep_retry_prompt_includes_command_hint_and_drops_invalid_first_text(tmp_path):
    fixture_path = tmp_path / "packet03_fixture.json"
    fixture_path.write_text(
        json.dumps(
            {
                "exercise_activation_contract": {
                    "require_live_tool_call": True,
                    "preferred_tool_name": "raw_bash",
                    "first_turn_tool_only_response": True,
                    "require_payload_observation_first": True,
                    "activation_payload_source_path": "workspace/a/payload.txt",
                    "retry_tool_call_command_hint": "cat workspace/a/payload.txt",
                    "suppress_first_no_tool_assistant_history": True,
                }
            }
        ),
        encoding="utf-8",
    )
    model = _ActivationContractRetryHistoryModel()

    result = baseline_execution_run_loop(
        model=model,
        tools={
            "raw_bash": lambda call: {
                "tool_name": "raw_bash",
                "command": call["arguments"]["command"],
                "exit_code": 0,
                "stdout": "payload\n",
                "stderr": "",
                "timed_out": False,
            }
        },
        context={
            "history": [{"role": "user", "content": "observe payload then edit target"}],
            "manage_history": full_history.manage,
            "env_info": {"cwd": str(tmp_path), "task_id": "workspace_target_regime_alpha"},
        },
        max_steps=1,
        tool_definitions=[{"name": "raw_bash"}],
    )

    assert model.calls == 2
    second_messages = model.messages_by_call[1]
    second_assistant_messages = [
        message.get("content")
        for message in second_messages
        if message.get("role") == "assistant"
    ]
    second_user_messages = [
        message.get("content")
        for message in second_messages
        if message.get("role") == "user"
    ]
    assert "draft no-tool response" not in second_assistant_messages
    assert any(
        isinstance(content, str) and "Use command: cat workspace/a/payload.txt." in content
        for content in second_user_messages
    )
    assert result["steps"][0]["status"] == "activation_contract_retry_due_to_no_tool_calls"
    assert result["steps"][1]["tool_calls"] == 1


def test_token_summary_uses_completion_usage_fields():
    summary = _token_and_cost_summary(
        {
            "execution": {
                "steps": [
                    {"completion": {"usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18, "usd": 0.01}}},
                    {"completion": {"usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8}}},
                ]
            }
        }
    )

    assert summary["input_tokens"] == 16
    assert summary["output_tokens"] == 10
    assert summary["total_tokens"] == 26
    assert summary["usd"] == 0.01


def test_completion_layer_contract_guard_emits_real_l0_l2_evidence(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_completion_layer_contract_guard"
    batch_spec = _single_eval_batch_spec(
        tmp_path=tmp_path,
        batch_id="packet03-completion-layer-semantic",
        eval_id=eval_id,
        execution_mode="deterministic_no_model",
    )

    run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: eval_cards[eval_id]},
    )

    batch_dir = tmp_path / batch_spec["batch_id"]
    record = _result_records(batch_dir)[0]
    trace = _trace_summaries(batch_dir)[0]
    score = _score_envelope_for_record(batch_dir, record)
    assert record["score_summary"]["final_verdict"] == "pass"
    assert record["failure_cluster"] == "none"
    assert score["layers"]["L0_inline_assertion"]["status"] == "pass"
    assert score["layers"]["L2_replay_or_state_grader"]["status"] == "pass"
    assert score["layers"]["L0_inline_assertion"]["evidence_refs"]
    assert score["layers"]["L2_replay_or_state_grader"]["evidence_refs"]
    assert trace["packet03_eval_summary"]["verification_reason_code_accuracy"] is True
    assert trace["packet03_eval_summary"]["verification_reason_code_coverage"] is True
    assert trace["packet03_eval_summary"]["mechanism_visibility_complete"] is True


def test_tool_call_shape_contract_uses_deterministic_matrix_grader(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_tool_call_shape_argument_contract"
    batch_spec = _single_eval_batch_spec(
        tmp_path=tmp_path,
        batch_id="packet03-tool-call-shape-semantic",
        eval_id=eval_id,
        execution_mode="deterministic_no_model",
    )
    batch_spec["evaluation_lane"] = "guardrail_debug"
    batch_spec["fixed_invariants"]["evaluation_lane"] = "guardrail_debug"
    eval_card = dict(eval_cards[eval_id])
    eval_card["evaluation_lane"] = "guardrail_debug"

    run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: eval_card},
    )

    batch_dir = tmp_path / batch_spec["batch_id"]
    record = _result_records(batch_dir)[0]
    trace = _trace_summaries(batch_dir)[0]
    score = _score_envelope_for_record(batch_dir, record)
    assert record["score_summary"]["final_verdict"] == "pass"
    assert record["failure_cluster"] == "none"
    assert score["layers"]["L0_inline_assertion"]["status"] == "pass"
    assert score["layers"]["L2_replay_or_state_grader"]["status"] == "pass"
    assert score["layers"]["L2_replay_or_state_grader"]["grader_id"] == "p03_tool_call_shape_grader_v1"
    assert trace["packet03_eval_summary"]["tool_call_shape_classifier_source"] == "runtime_probe"
    assert trace["packet03_eval_summary"]["tool_contract_cases_total"] == 5
    assert trace["packet03_eval_summary"]["tool_contract_cases_matched"] == 5
    assert trace["packet03_eval_summary"]["mechanism_visibility_complete"] is True
    assert trace["packet03_eval_summary"]["helper_only_evidence"] is False


def test_lifecycle_terminality_guard_emits_deterministic_l0_l2_evidence(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_lifecycle_terminality_contract_guard"
    batch_spec = _single_eval_batch_spec(
        tmp_path=tmp_path,
        batch_id="packet03-lifecycle-semantic",
        eval_id=eval_id,
        execution_mode="deterministic_no_model",
    )

    run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: eval_cards[eval_id]},
    )

    batch_dir = tmp_path / batch_spec["batch_id"]
    record = _result_records(batch_dir)[0]
    trace = _trace_summaries(batch_dir)[0]
    score = _score_envelope_for_record(batch_dir, record)
    assert record["score_summary"]["final_verdict"] == "pass"
    assert record["failure_cluster"] == "none"
    assert "required_layer_missing_l0_inline_assertion" not in record["reason_codes"]
    assert "required_layer_missing_l2_replay_or_state_grader" not in record["reason_codes"]
    assert score["layers"]["L0_inline_assertion"]["status"] == "pass"
    assert score["layers"]["L2_replay_or_state_grader"]["status"] == "pass"
    assert score["layers"]["L0_inline_assertion"]["evidence_refs"]
    assert score["layers"]["L2_replay_or_state_grader"]["evidence_refs"]
    assert trace["packet03_eval_summary"]["terminality_tuple_coherent"] is True
    assert trace["packet03_eval_summary"]["terminal_write_count_observed"] == 1
    assert trace["packet03_eval_summary"]["cleanup_completed"] is True
    assert trace["packet03_eval_summary"]["mechanism_visibility_complete"] is True


def test_lifecycle_terminality_guard_distinguishes_runtime_mismatch_as_fail(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_lifecycle_terminality_contract_guard"
    route = {"eval_id": eval_id, "eval_card": eval_cards[eval_id]}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "task-001",
            "task_prompt": "semantic probe",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "lifecycle-runtime-mismatch",
    )
    tuple_data = fixture_plan["fixture"]["terminality_tuple"]
    tuple_data["expected_terminal_state"] = "error"
    tuple_data["terminal_state_flags"] = {
        "completed": False,
        "error": True,
        "max_steps_exhausted": False,
    }
    execution_result = _seed_execution_result(eval_id)
    graded = apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    score = graded["score_envelope"]
    reason_codes = set(score["layers"]["L2_replay_or_state_grader"]["reason_codes"])
    assert score["aggregate"]["final_verdict"] == "fail"
    assert score["layers"]["L0_inline_assertion"]["status"] == "pass"
    assert score["layers"]["L2_replay_or_state_grader"]["status"] == "fail"
    assert "lifecycle_terminality_status_mismatch" in reason_codes
    assert "required_layer_missing_l2_replay_or_state_grader" not in reason_codes


def test_completion_layer_contract_guard_requires_verification_telemetry(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_completion_layer_contract_guard"
    route = {"eval_id": eval_id, "eval_card": eval_cards[eval_id]}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "task-001",
            "task_prompt": "semantic probe",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "completion-no-verification",
    )
    execution_result = _seed_execution_result(eval_id)
    execution_result["verification"] = {}
    graded = apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    score = graded["score_envelope"]
    assert score["aggregate"]["final_verdict"] == "unresolved"
    assert "verification_mechanism_evidence_missing" in score["layers"]["L2_replay_or_state_grader"]["reason_codes"]


def test_verification_reason_code_quality_v2_fails_baseline_positive_proxy(tmp_path):
    eval_id = "ae_verification_reason_code_quality_v2"
    batch_spec = _single_eval_batch_spec(
        tmp_path=tmp_path,
        batch_id="packet05a-verification-quality-semantic",
        eval_id=eval_id,
        execution_mode="deterministic_no_model",
    )
    batch_spec["task_cases"] = [
        {
            "task_id": "verification_missing_l1_non_substitution",
            "task_prompt": "packet05a verification quality semantic probe",
        }
    ]

    run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: _verification_v2_eval_card()},
    )

    batch_dir = tmp_path / batch_spec["batch_id"]
    record = _result_records(batch_dir)[0]
    trace = _trace_summaries(batch_dir)[0]
    score = _score_envelope_for_record(batch_dir, record)
    assert record["score_summary"]["final_verdict"] == "fail"
    assert record["failure_cluster"] == "completion_false_positive"
    assert score["layers"]["L2_replay_or_state_grader"]["status"] == "fail"
    reason_codes = set(score["layers"]["L2_replay_or_state_grader"]["reason_codes"])
    assert "verification_reason_code_verified_mismatch" in reason_codes
    assert "verification_substitution_violation_mismatch" in reason_codes
    assert trace["packet03_eval_summary"]["mechanism_visibility_complete"] is True


def test_lifecycle_adversarial_terminality_v2_fails_baseline_cleanup_race_proxy(tmp_path):
    eval_id = "ae_lifecycle_adversarial_terminality_v2"
    batch_spec = _single_eval_batch_spec(
        tmp_path=tmp_path,
        batch_id="packet05a-lifecycle-adversarial-semantic",
        eval_id=eval_id,
        execution_mode="deterministic_no_model",
    )
    batch_spec["task_cases"] = [
        {
            "task_id": "lifecycle_cleanup_race_incomplete_cleanup",
            "task_prompt": "packet05a lifecycle adversarial semantic probe",
        }
    ]

    run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: _lifecycle_v2_eval_card()},
    )

    batch_dir = tmp_path / batch_spec["batch_id"]
    record = _result_records(batch_dir)[0]
    trace = _trace_summaries(batch_dir)[0]
    score = _score_envelope_for_record(batch_dir, record)
    assert record["score_summary"]["final_verdict"] == "fail"
    assert record["failure_cluster"] == "process_lifecycle_and_cancellation_boundary_failure"
    assert score["layers"]["L2_replay_or_state_grader"]["status"] == "fail"
    reason_codes = set(score["layers"]["L2_replay_or_state_grader"]["reason_codes"])
    assert "lifecycle_adversarial_status_mismatch" in reason_codes
    assert "lifecycle_adversarial_reason_code_mismatch" in reason_codes
    assert trace["packet03_eval_summary"]["mechanism_visibility_complete"] is True
    assert trace["packet03_eval_summary"]["cleanup_completed"] is False


def test_lifecycle_terminality_guard_uses_observed_runtime_state_not_fixture_tuple(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_lifecycle_terminality_contract_guard"
    route = {"eval_id": eval_id, "eval_card": eval_cards[eval_id]}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "task-001",
            "task_prompt": "semantic probe",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "lifecycle-observed-runtime",
    )
    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["terminal_write_count"] = 2
    execution_result["execution"]["lifecycle_reason_codes"] = ["lifecycle_terminal_write_count_invalid"]
    graded = apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    reason_codes = set(graded["score_envelope"]["layers"]["L2_replay_or_state_grader"]["reason_codes"])
    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "fail"
    assert "lifecycle_terminality_single_terminal_write_violation" in reason_codes


def test_cwd_path_guard_emits_deterministic_l0_l2_evidence(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_cwd_workdir_path_contract_guard"
    batch_spec = _single_eval_batch_spec(
        tmp_path=tmp_path,
        batch_id="packet03-cwd-path-semantic",
        eval_id=eval_id,
        execution_mode="deterministic_no_model",
    )

    run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: eval_cards[eval_id]},
    )

    batch_dir = tmp_path / batch_spec["batch_id"]
    record = _result_records(batch_dir)[0]
    trace = _trace_summaries(batch_dir)[0]
    score = _score_envelope_for_record(batch_dir, record)
    assert record["score_summary"]["final_verdict"] == "pass"
    assert record["failure_cluster"] == "none"
    assert "required_layer_missing_l0_inline_assertion" not in record["reason_codes"]
    assert "required_layer_missing_l2_replay_or_state_grader" not in record["reason_codes"]
    assert score["layers"]["L0_inline_assertion"]["status"] == "pass"
    assert score["layers"]["L2_replay_or_state_grader"]["status"] == "pass"
    assert score["layers"]["L0_inline_assertion"]["evidence_refs"]
    assert score["layers"]["L2_replay_or_state_grader"]["evidence_refs"]
    assert trace["packet03_eval_summary"]["cwd_path_tuple_coherent"] is True


def test_cwd_path_guard_distinguishes_incomplete_tuple_as_unresolved(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_cwd_workdir_path_contract_guard"
    route = {"eval_id": eval_id, "eval_card": eval_cards[eval_id]}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "task-001",
            "task_prompt": "semantic probe",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "cwd-path-unresolved",
    )
    del fixture_plan["fixture"]["path_contract_tuple"]["normalized_target_path"]
    execution_result = _seed_execution_result(eval_id)
    graded = apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    score = graded["score_envelope"]
    reason_codes = set(score["layers"]["L2_replay_or_state_grader"]["reason_codes"])
    assert score["aggregate"]["final_verdict"] == "unresolved"
    assert score["layers"]["L0_inline_assertion"]["status"] == "fail"
    assert score["layers"]["L2_replay_or_state_grader"]["status"] == "fail"
    assert "cwd_path_contract_tuple_incomplete" in reason_codes
    assert "required_layer_missing_l2_replay_or_state_grader" not in reason_codes


def test_completion_contradiction_probe_uses_repaired_deterministic_contract(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_completion_verifier_final_contradiction_probe"
    batch_spec = _single_eval_batch_spec(
        tmp_path=tmp_path,
        batch_id="packet03-completion-semantic",
        eval_id=eval_id,
        execution_mode="offline_judge_batchable",
    )

    run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: eval_cards[eval_id]},
        model_route_override=LocalStubModelClient.create(response_text="done").route,
    )

    batch_dir = tmp_path / batch_spec["batch_id"]
    record = _result_records(batch_dir)[0]
    trace = _trace_summaries(batch_dir)[0]
    score = _score_envelope_for_record(batch_dir, record)
    assert record["score_summary"]["final_verdict"] == "pass"
    assert record["failure_cluster"] == "none"
    assert score["layers"]["L0_inline_assertion"]["status"] == "pass"
    assert score["layers"]["L2_replay_or_state_grader"]["status"] == "pass"
    assert score["layers"]["L3_judge_layer"]["status"] == "pass"
    assert score["layers"]["L3_judge_layer"]["judge_config"]["mode"] == "phase15_measurement_repair"
    assert "pinned_offline_judge_not_implemented_packet03" not in record["reason_codes"]
    assert "required_layer_missing_l3_judge_layer" not in record["reason_codes"]
    assert "bounded_l3_dependency" not in record["promotion_blocker_codes"]
    assert trace["packet03_eval_summary"]["phase15_repaired_contradiction_surface"] is True
    assert trace["packet03_eval_summary"]["contradiction_detected"] is True
    assert trace["packet03_eval_summary"]["contradiction_contract_match"] is True


def test_workspace_probe_requires_target_mechanism_evidence(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_workspace_target_correctness_probe"
    batch_spec = _single_eval_batch_spec(
        tmp_path=tmp_path,
        batch_id="packet03-workspace-semantic",
        eval_id=eval_id,
        execution_mode="one_shot_batchable",
    )

    run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: eval_cards[eval_id]},
        model_route_override=LocalStubModelClient.create(response_text="done").route,
    )

    batch_dir = tmp_path / batch_spec["batch_id"]
    record = _result_records(batch_dir)[0]
    trace = _trace_summaries(batch_dir)[0]
    score = _score_envelope_for_record(batch_dir, record)
    assert record["score_summary"]["final_verdict"] == "pass"
    assert record["failure_cluster"] == "none"
    assert score["layers"]["L2_replay_or_state_grader"]["status"] == "pass"
    assert trace["packet03_eval_summary"]["workspace_target_hit"] is True
    assert trace["packet03_eval_summary"]["workspace_decoys_preserved"] is True
    assert trace["packet03_eval_summary"]["workspace_target_content_ok"] is True


def test_workspace_probe_distinguishes_no_tool_path_as_unresolved(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_workspace_target_correctness_probe"
    route = {"eval_id": eval_id, "eval_card": eval_cards[eval_id]}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "task-001",
            "task_prompt": "semantic probe",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "workspace-no-tool",
    )
    execution_result = _seed_execution_result(eval_id)
    graded = apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "unresolved"
    assert (
        "workspace_target_probe_not_exercised_no_tool_calls"
        in graded["score_envelope"]["layers"]["L2_replay_or_state_grader"]["reason_codes"]
    )


def test_workspace_probe_downgrades_model_execution_error_even_if_probe_succeeds(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_workspace_target_correctness_probe"
    route = {"eval_id": eval_id, "eval_card": eval_cards[eval_id]}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "task-001",
            "task_prompt": "semantic probe",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "workspace-execution-error",
    )
    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["status"] = "error"
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 1,
            "status": "forced_runtime_probe",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": "printf 'packet03_target_updated\\n' > workspace/target/answer.txt",
                    "exit_code": 0,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 0, "output_tokens": 0}},
        }
    ]
    execution_result["run_events"] = [
        {
            "event_type": "model_client_error",
            "payload": {"details": {"response_body": '{"detail":"Unsupported tool type: None"}'}},
        }
    ]
    graded = apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "unresolved"
    assert "model_execution_error" in graded["score_envelope"]["layers"]["L4_final_acceptance"]["reason_codes"]


def test_workspace_target_decoy_generalization_v2_emits_explicit_target_decoy_trace(tmp_path):
    eval_id = "ae_workspace_target_decoy_generalization_v2"
    route = {"eval_id": eval_id, "eval_card": _workspace_target_decoy_generalization_v2_eval_card()}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "p04_workspace_target_decoy_resistance_atomic_v1",
            "task_id": "workspace_target_regime_beta",
            "task_prompt": "workspace-target decoy generalization",
            "rerun_index": 1,
        },
        run_dir=tmp_path / "workspace-target-decoy-generalization-pass",
    )
    fixture = fixture_plan["fixture"]
    target = fixture["target_descriptor"]
    run_dir = Path(fixture_plan["fixture_ref"]).resolve().parent
    (run_dir / target["path"]).write_text(target["expected_text"], encoding="utf-8")

    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 1,
            "status": "tool_executed",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": f"printf 'updated\\n' > {target['path']}",
                    "exit_code": 0,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 0, "output_tokens": 0}},
        }
    ]
    execution_result["execution"]["step_count"] = 1

    graded = apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    trace = graded["packet03_eval_trace"]
    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "pass"
    assert trace["workspace_target_regime_count"] >= 2
    assert trace["workspace_target_transfer_tier"] == "development_transfer"
    assert trace["workspace_target_target_id"]
    assert trace["workspace_target_decoy_ids"]
    assert trace["workspace_target_target_touch_evidence"]
    assert trace["workspace_target_decoy_touch_evidence"] == []
    assert trace["workspace_target_forced_probe_observed"] is False
    assert trace["workspace_target_trace_linkage_complete"] is True
    assert trace["mechanism_visibility_complete"] is True


def test_workspace_target_decoy_generalization_v2_fixture_requires_live_tool_activation(tmp_path):
    eval_id = "ae_workspace_target_decoy_generalization_v2"
    route = {"eval_id": eval_id, "eval_card": _workspace_target_decoy_generalization_v2_eval_card()}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "p04_workspace_target_decoy_resistance_atomic_v1",
            "task_id": "workspace_target_regime_alpha",
            "task_prompt": "workspace-target decoy generalization",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "workspace-target-decoy-generalization-activation-contract",
    )
    fixture = fixture_plan["fixture"]
    target = fixture["target_descriptor"]
    activation_payload = fixture["activation_payload_descriptor"]
    activation_contract = fixture["exercise_activation_contract"]
    prompt = fixture_plan["task_prompt"]

    assert fixture_plan["model_client_kwargs"] is None
    assert fixture_plan["exercise_activation_contract"] == activation_contract
    assert activation_contract["require_live_tool_call"] is True
    assert activation_contract["preferred_tool_name"] == "raw_bash"
    assert activation_contract["first_turn_tool_only_response"] is True
    assert activation_contract["require_payload_copy_from_source"] is True
    assert activation_contract["forbid_forced_probe_satisfier"] is True
    assert activation_contract["fail_closed_reason_code"] == (
        "workspace_target_decoy_generalization_not_exercised_no_tool_calls"
    )
    assert activation_payload["source_path"]
    assert activation_payload["copy_command_example"]
    assert activation_payload["expected_text_disclosed_in_prompt"] is False
    assert target["path"] in prompt
    assert activation_payload["source_path"] in prompt
    assert target["expected_text"].strip() not in prompt
    assert "emit exactly one raw_bash tool call and no prose" in prompt
    assert "Plain-text/no-tool responses are scored as not exercised." in prompt


def test_workspace_target_decoy_generalization_v2_fails_closed_without_tool_evidence(tmp_path):
    eval_id = "ae_workspace_target_decoy_generalization_v2"
    route = {"eval_id": eval_id, "eval_card": _workspace_target_decoy_generalization_v2_eval_card()}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "p04_workspace_target_decoy_resistance_atomic_v1",
            "task_id": "workspace_target_regime_alpha",
            "task_prompt": "workspace-target decoy generalization",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "workspace-target-decoy-generalization-no-tools",
    )
    execution_result = _seed_execution_result(eval_id)
    graded = apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    reason_codes = set(graded["score_envelope"]["layers"]["L2_replay_or_state_grader"]["reason_codes"])
    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "unresolved"
    assert "workspace_target_decoy_generalization_not_exercised_no_tool_calls" in reason_codes
    assert graded["packet03_eval_trace"]["mechanism_visibility_complete"] is False
    assert graded["packet03_eval_trace"]["schema_complete_for_promotion"] is False


def test_workspace_target_decoy_generalization_v2_rejects_forced_probe_contamination(tmp_path):
    eval_id = "ae_workspace_target_decoy_generalization_v2"
    route = {"eval_id": eval_id, "eval_card": _workspace_target_decoy_generalization_v2_eval_card()}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "p04_workspace_target_decoy_resistance_atomic_v1",
            "task_id": "workspace_target_regime_alpha",
            "task_prompt": "workspace-target decoy generalization",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "workspace-target-decoy-generalization-forced-probe",
    )
    fixture = fixture_plan["fixture"]
    target = fixture["target_descriptor"]
    run_dir = Path(fixture_plan["fixture_ref"]).resolve().parent
    (run_dir / target["path"]).write_text(target["expected_text"], encoding="utf-8")

    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 1,
            "status": "forced_runtime_probe",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": f"printf 'updated\\n' > {target['path']}",
                    "exit_code": 0,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 0, "output_tokens": 0}},
        }
    ]
    execution_result["execution"]["step_count"] = 1
    execution_result["run_events"] = [
        {
            "event_type": "raw_bash_result",
            "payload": {"details": {"forced_probe": True}},
        }
    ]
    graded = apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    reason_codes = set(graded["score_envelope"]["layers"]["L2_replay_or_state_grader"]["reason_codes"])
    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "unresolved"
    assert "workspace_target_decoy_generalization_forced_probe_contamination" in reason_codes
    assert graded["packet03_eval_trace"]["workspace_target_forced_probe_observed"] is True


def test_workspace_target_multistep_v1_fixture_declares_turn_contract(tmp_path):
    eval_id = "ae_workspace_target_decoy_generalization_multistep_v1"
    route = {"eval_id": eval_id, "eval_card": _workspace_target_decoy_multistep_v1_eval_card()}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "p04_workspace_target_decoy_resistance_atomic_v1",
            "task_id": "workspace_target_regime_alpha",
            "task_prompt": "workspace-target multistep",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "workspace-target-multistep-fixture",
    )
    fixture = fixture_plan["fixture"]
    turn_contract = fixture["multistep_turn_contract"]
    activation_contract = fixture["exercise_activation_contract"]

    assert fixture["surface_alias"] == "eval_workspace_target_decoy_generalization_multistep_v1"
    assert turn_contract["minimum_turn_count"] == 2
    assert turn_contract["require_first_turn_tool_observation"] is True
    assert turn_contract["require_post_observation_step"] is True
    assert turn_contract["require_target_touch_after_observation"] is True
    assert activation_contract["require_payload_observation_first"] is True
    assert activation_contract["require_second_turn_decision_or_edit"] is True
    assert activation_contract["activation_payload_source_path"] == fixture["activation_payload_descriptor"]["source_path"]
    assert activation_contract["retry_tool_call_command_hint"] == (
        f"cat {fixture['activation_payload_descriptor']['source_path']}"
    )
    assert activation_contract["suppress_first_no_tool_assistant_history"] is True
    assert activation_contract["fail_closed_reason_code"] == "workspace_target_multistep_turn_contract_not_satisfied"


def test_workspace_target_multistep_v1_emits_turn_contract_trace_and_passes_with_two_step_evidence(tmp_path):
    eval_id = "ae_workspace_target_decoy_generalization_multistep_v1"
    route = {"eval_id": eval_id, "eval_card": _workspace_target_decoy_multistep_v1_eval_card()}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "p04_workspace_target_decoy_resistance_atomic_v1",
            "task_id": "workspace_target_regime_beta",
            "task_prompt": "workspace-target multistep",
            "rerun_index": 1,
        },
        run_dir=tmp_path / "workspace-target-multistep-pass",
    )
    fixture = fixture_plan["fixture"]
    target = fixture["target_descriptor"]
    source = fixture["activation_payload_descriptor"]["source_path"]
    run_dir = Path(fixture_plan["fixture_ref"]).resolve().parent
    (run_dir / target["path"]).write_text(target["expected_text"], encoding="utf-8")

    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 1,
            "status": "tool_executed",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": f"cat {source}",
                    "exit_code": 0,
                    "stdout": target["expected_text"],
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 0, "output_tokens": 0}},
        },
        {
            "step": 1,
            "tool_calls": 1,
            "status": "tool_executed",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": f"cat {source} > {target['path']}",
                    "exit_code": 0,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "updated", "tool_calls": [], "usage": {"input_tokens": 0, "output_tokens": 0}},
        },
    ]
    execution_result["execution"]["step_count"] = 2

    graded = apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    trace = graded["packet03_eval_trace"]
    reason_codes = set(graded["score_envelope"]["layers"]["L2_replay_or_state_grader"]["reason_codes"])
    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "pass"
    assert "workspace_target_multistep_turn_contract_not_satisfied" not in reason_codes
    assert trace["workspace_target_multistep_turn_count"] == 2
    assert trace["workspace_target_multistep_first_tool_step_index"] == 0
    assert trace["workspace_target_multistep_first_turn_observation_met"] is True
    assert trace["workspace_target_multistep_post_observation_step_met"] is True
    assert trace["workspace_target_multistep_target_touch_after_observation"] is True
    assert trace["workspace_target_multistep_contract_satisfied"] is True
    assert trace["workspace_target_first_turn_observation_evidence"]
    assert trace["workspace_target_post_observation_target_touch_evidence"]
    assert trace["mechanism_visibility_complete"] is True


def test_workspace_target_multistep_v1_fails_closed_when_turn_contract_is_missing(tmp_path):
    eval_id = "ae_workspace_target_decoy_generalization_multistep_v1"
    route = {"eval_id": eval_id, "eval_card": _workspace_target_decoy_multistep_v1_eval_card()}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "p04_workspace_target_decoy_resistance_atomic_v1",
            "task_id": "workspace_target_regime_alpha",
            "task_prompt": "workspace-target multistep",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "workspace-target-multistep-missing-turn",
    )
    fixture = fixture_plan["fixture"]
    target = fixture["target_descriptor"]
    run_dir = Path(fixture_plan["fixture_ref"]).resolve().parent
    (run_dir / target["path"]).write_text(target["expected_text"], encoding="utf-8")
    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 1,
            "status": "tool_executed",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": f"printf 'updated\\n' > {target['path']}",
                    "exit_code": 0,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 0, "output_tokens": 0}},
        }
    ]
    execution_result["execution"]["step_count"] = 1

    graded = apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    reason_codes = set(graded["score_envelope"]["layers"]["L2_replay_or_state_grader"]["reason_codes"])
    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "unresolved"
    assert "workspace_target_multistep_turn_contract_not_satisfied" in reason_codes
    assert graded["packet03_eval_trace"]["workspace_target_multistep_contract_satisfied"] is False
    assert graded["packet03_eval_trace"]["mechanism_visibility_complete"] is False


def test_tool_result_normalization_probe_requires_runtime_category_evidence(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_tool_result_normalization_permission_probe"
    batch_spec = _single_eval_batch_spec(
        tmp_path=tmp_path,
        batch_id="packet03-tool-result-normalization-semantic",
        eval_id=eval_id,
        execution_mode="one_shot_batchable",
    )

    run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: eval_cards[eval_id]},
        model_route_override=LocalStubModelClient.create(response_text="done").route,
    )

    batch_dir = tmp_path / batch_spec["batch_id"]
    record = _result_records(batch_dir)[0]
    trace = _trace_summaries(batch_dir)[0]
    score = _score_envelope_for_record(batch_dir, record)
    assert record["score_summary"]["final_verdict"] == "pass"
    assert record["failure_cluster"] == "none"
    assert score["layers"]["L0_inline_assertion"]["status"] == "pass"
    assert score["layers"]["L2_replay_or_state_grader"]["status"] == "pass"
    observed_categories = set(trace["packet03_eval_summary"]["observed_tool_result_categories"])
    assert {"permission_denied", "runtime_error"}.issubset(observed_categories)


def test_run_batch_preserves_packet05_claim_route_and_budget_aliases(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_tool_result_normalization_permission_probe"
    batch_spec = _single_eval_batch_spec(
        tmp_path=tmp_path,
        batch_id="packet05b-claim-route-budget-aliases",
        eval_id=eval_id,
        execution_mode="one_shot_batchable",
    )
    batch_spec["packet_stage"] = "packet_05"
    batch_spec["evaluation_lane"] = "guardrail_debug"
    batch_spec["promotion_authority"] = False
    batch_spec["fixed_invariants"]["evaluation_lane"] = "guardrail_debug"
    batch_spec["claim_route_id"] = "cr_v04_tb_02"
    batch_spec["task_intent"] = "permission_runtime_failure_cause"
    batch_spec["budget_cap_usd"] = 1.0
    batch_spec["task_cases"] = [
        {
            "task_id": "tool_result_live_cases",
            "task_prompt": "packet05b tool result attribution contract probe",
            "claim_route_id": "cr_v04_tb_02",
            "task_intent": "permission_runtime_failure_cause",
        }
    ]

    run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: eval_cards[eval_id]},
        model_route_override=LocalStubModelClient.create(response_text="done").route,
    )

    batch_dir = tmp_path / batch_spec["batch_id"]
    record = _result_records(batch_dir)[0]
    trace = _trace_summaries(batch_dir)[0]

    assert record["claim_route_id"] == "cr_v04_tb_02"
    assert record["task_intent"] == "permission_runtime_failure_cause"
    assert record["contender_id"] == "sc_b_01"
    assert record["budget_cap_usd"] == 1.0
    assert "budget_spend_usd" in record
    assert "usd_estimate" in record["token_and_cost_summary"]
    assert trace["claim_route_id"] == "cr_v04_tb_02"
    assert trace["task_intent"] == "permission_runtime_failure_cause"


def test_project_owned_pd_evals_are_admitted_to_promotion_lane():
    for eval_id in (
        "ae_internal_discovery_evidence_efficiency_v1",
        "ae_internal_multifile_repair_test_verify_v1",
        "ae_internal_toolchain_dependency_pressure_v1",
        "ae_internal_artifact_log_extraction_v1",
    ):
        policy = get_packet03_eval_lane_policy(eval_id)
        assert policy["default_evaluation_lane"] == "promotion"
        assert policy["promotion_blocker_codes"] == []


def test_phase15_env_and_artifact_eval_cards_are_active():
    eval_cards = _load_active_eval_cards()
    for eval_id in (
        "ae_internal_toolchain_dependency_pressure_v1",
        "ae_internal_artifact_log_extraction_v1",
    ):
        card = eval_cards[eval_id]
        assert card["evaluation_lane"] == "promotion"
        assert card["execution_mode"] == "multistep_batchable"
        assert card["fixed_invariants"]["comparator_variant_id"] == "spb_01"
        assert card["score_layer_expectations"]["l3_llm_judge"] == "not_applicable"


def test_successor_trace_summary_separates_declared_vs_observed_mechanisms(tmp_path):
    eval_cards = _load_active_eval_cards()
    batch_spec = _successor_smoke_batch_spec(tmp_path=tmp_path, batch_id="successor-smoke-trace-marker-contract")
    run_batch(
        batch_spec=batch_spec,
        eval_cards=eval_cards,
        model_route_override=LocalStubModelClient.create(response_text="done").route,
    )
    batch_dir = tmp_path / batch_spec["batch_id"]
    traces = _trace_summaries(batch_dir)
    assert traces
    rhv1_traces = [row for row in traces if row.get("variant_id") == "rhv1_ref_01"]
    spb_traces = [row for row in traces if row.get("variant_id") == "spb_01"]
    assert rhv1_traces and spb_traces
    for row in rhv1_traces:
        assert "declared_mechanisms" in row
        observed = row["observed_mechanisms"]
        assert observed["marker_family"] == "rhv1_observed_markers.v1"
        assert set(observed["markers"]) == set(SUCCESSOR_RHV1_OBSERVED_MARKER_IDS)
    for row in spb_traces:
        assert "declared_mechanisms" in row
        observed = row["observed_mechanisms"]
        assert observed["marker_family"] == "none"
        assert observed["markers"] == {}


def test_successor_trace_summary_fails_closed_when_rhv1_markers_absent(tmp_path):
    eval_cards = _load_active_eval_cards()
    batch_spec = _successor_smoke_batch_spec(tmp_path=tmp_path, batch_id="successor-smoke-trace-marker-fail-closed-rhv1")
    run_batch(
        batch_spec=batch_spec,
        eval_cards=eval_cards,
        model_route_override=LocalStubModelClient.create(response_text="done").route,
    )
    batch_dir = tmp_path / batch_spec["batch_id"]
    trace = next(row for row in _trace_summaries(batch_dir) if row.get("variant_id") == "rhv1_ref_01")
    missing_marker = SUCCESSOR_RHV1_OBSERVED_MARKER_IDS[0]
    trace["observed_mechanisms"]["markers"].pop(missing_marker, None)
    with pytest.raises(SchemaValidationError):
        validate_trace_summary(trace)


def test_successor_trace_summary_fails_closed_when_spb_emits_rhv1_markers(tmp_path):
    eval_cards = _load_active_eval_cards()
    batch_spec = _successor_smoke_batch_spec(tmp_path=tmp_path, batch_id="successor-smoke-trace-marker-fail-closed-spb")
    run_batch(
        batch_spec=batch_spec,
        eval_cards=eval_cards,
        model_route_override=LocalStubModelClient.create(response_text="done").route,
    )
    batch_dir = tmp_path / batch_spec["batch_id"]
    trace = next(row for row in _trace_summaries(batch_dir) if row.get("variant_id") == "spb_01")
    trace["observed_mechanisms"]["marker_family"] = "rhv1_observed_markers.v1"
    trace["observed_mechanisms"]["markers"] = {
        SUCCESSOR_RHV1_OBSERVED_MARKER_IDS[0]: {"observed": True, "evidence_refs": ["x"]}
    }
    with pytest.raises(SchemaValidationError):
        validate_trace_summary(trace)


def test_internal_toolchain_dependency_pressure_v1_grader_passes_with_contract_matrix(tmp_path):
    eval_id = "ae_internal_toolchain_dependency_pressure_v1"
    eval_card = _internal_toolchain_dependency_pressure_eval_card()
    route = {"eval_id": eval_id, "eval_card": eval_card}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "v04_tb_01_tool_call_contract_classifier",
            "task_id": "p06_combo_tool_gateway_01_toolchain_pressure",
            "task_prompt": "toolchain corroboration",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "internal-toolchain-pressure-pass",
    )
    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 3,
            "status": "forced_runtime_probe",
            "results": [
                {
                    "case_id": "valid_dict_case",
                    "tool_call_contract_class": "valid_call",
                    "result_class": "success",
                    "reason_code": "tool_success",
                },
                {
                    "case_id": "plain_string_arguments_case",
                    "tool_call_contract_class": "malformed_call",
                    "result_class": "contract_error",
                    "reason_code": "tool_call_contract_malformed",
                },
                {
                    "case_id": "malformed_json_string_case",
                    "tool_call_contract_class": "malformed_call",
                    "result_class": "contract_error",
                    "reason_code": "tool_call_contract_malformed",
                },
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 0, "output_tokens": 0}},
        }
    ]
    execution_result["execution"]["step_count"] = 1

    graded = apply_packet03_eval_grader(route=route, execution_result=execution_result, fixture_plan=fixture_plan)
    trace = graded["packet03_eval_trace"]

    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "pass"
    assert graded["score_envelope"]["layers"]["L2_replay_or_state_grader"]["status"] == "pass"
    assert trace["toolchain_pressure_trace_complete"] is True
    assert trace["toolchain_pressure_cases_matched"] == trace["toolchain_pressure_cases_total"]


def test_internal_toolchain_dependency_pressure_v1_grader_fails_on_legacy_shape_acceptance(tmp_path):
    eval_id = "ae_internal_toolchain_dependency_pressure_v1"
    eval_card = _internal_toolchain_dependency_pressure_eval_card()
    route = {"eval_id": eval_id, "eval_card": eval_card}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "p06_combo_tool_gateway_01_toolchain_pressure",
            "task_prompt": "toolchain corroboration",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "internal-toolchain-pressure-fail",
    )
    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 3,
            "status": "forced_runtime_probe",
            "results": [
                {
                    "case_id": "valid_dict_case",
                    "tool_call_contract_class": "valid_call",
                    "result_class": "success",
                    "reason_code": "tool_success",
                },
                {
                    "case_id": "plain_string_arguments_case",
                    "tool_call_contract_class": "valid_call",
                    "result_class": "success",
                    "reason_code": "tool_success",
                },
                {
                    "case_id": "malformed_json_string_case",
                    "tool_call_contract_class": "valid_call",
                    "result_class": "runtime_error",
                    "reason_code": "tool_runtime_nonzero_exit",
                },
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 0, "output_tokens": 0}},
        }
    ]
    execution_result["execution"]["step_count"] = 1

    graded = apply_packet03_eval_grader(route=route, execution_result=execution_result, fixture_plan=fixture_plan)
    reason_codes = set(graded["score_envelope"]["layers"]["L2_replay_or_state_grader"]["reason_codes"])

    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "fail"
    assert "toolchain_dependency_contract_mismatch" in reason_codes


def test_internal_artifact_log_extraction_v1_grader_passes_with_attribution_matrix(tmp_path):
    eval_id = "ae_internal_artifact_log_extraction_v1"
    eval_card = _internal_artifact_log_extraction_eval_card()
    route = {"eval_id": eval_id, "eval_card": eval_card}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "v04_tb_02_permission_runtime_attribution_split",
            "task_id": "p06_combo_tool_gateway_01_artifact_log",
            "task_prompt": "artifact/log corroboration",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "internal-artifact-log-pass",
    )
    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 3,
            "status": "forced_runtime_probe",
            "results": [
                {
                    "case_id": "permission_live_case",
                    "result_class": "permission_denied",
                    "reason_code": "tool_permission_denied",
                    "attribution_trace": {"permission_signal_detected": True, "runtime_signal_detected": False},
                },
                {
                    "case_id": "mixed_fault_live_case",
                    "result_class": "runtime_error",
                    "reason_code": "tool_runtime_mixed_permission_runtime_signals",
                    "attribution_trace": {"permission_signal_detected": True, "runtime_signal_detected": True},
                },
                {
                    "case_id": "success_live_case",
                    "result_class": "success",
                    "reason_code": "tool_success",
                    "attribution_trace": {"permission_signal_detected": False, "runtime_signal_detected": False},
                },
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 0, "output_tokens": 0}},
        }
    ]
    execution_result["execution"]["step_count"] = 1

    graded = apply_packet03_eval_grader(route=route, execution_result=execution_result, fixture_plan=fixture_plan)
    trace = graded["packet03_eval_trace"]

    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "pass"
    assert graded["score_envelope"]["layers"]["L2_replay_or_state_grader"]["status"] == "pass"
    assert trace["artifact_log_trace_complete"] is True
    assert set(trace["observed_tool_result_categories"]) == {"permission_denied", "runtime_error", "success"}


def test_internal_artifact_log_extraction_v1_fails_closed_when_attribution_trace_missing(tmp_path):
    eval_id = "ae_internal_artifact_log_extraction_v1"
    eval_card = _internal_artifact_log_extraction_eval_card()
    route = {"eval_id": eval_id, "eval_card": eval_card}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "p06_combo_tool_gateway_01_artifact_log",
            "task_prompt": "artifact/log corroboration",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "internal-artifact-log-missing-trace",
    )
    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 3,
            "status": "forced_runtime_probe",
            "results": [
                {
                    "case_id": "permission_live_case",
                    "result_class": "permission_denied",
                    "reason_code": "tool_permission_denied",
                    "attribution_trace": {"permission_signal_detected": True, "runtime_signal_detected": False},
                },
                {
                    "case_id": "mixed_fault_live_case",
                    "result_class": "permission_denied",
                    "reason_code": "tool_permission_denied",
                },
                {
                    "case_id": "success_live_case",
                    "result_class": "success",
                    "reason_code": "tool_success",
                    "attribution_trace": {"permission_signal_detected": False, "runtime_signal_detected": False},
                },
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 0, "output_tokens": 0}},
        }
    ]
    execution_result["execution"]["step_count"] = 1

    graded = apply_packet03_eval_grader(route=route, execution_result=execution_result, fixture_plan=fixture_plan)
    reason_codes = set(graded["score_envelope"]["layers"]["L2_replay_or_state_grader"]["reason_codes"])

    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "unresolved"
    assert "artifact_log_runtime_evidence_missing" in reason_codes


def test_internal_corroboration_evals_emit_tool_family_governed_truth(tmp_path):
    eval_cards = {
        "ae_internal_toolchain_dependency_pressure_v1": _internal_toolchain_dependency_pressure_eval_card(),
        "ae_internal_artifact_log_extraction_v1": _internal_artifact_log_extraction_eval_card(),
    }
    for eval_id in eval_cards:
        batch_spec = _single_eval_batch_spec(
            tmp_path=tmp_path,
            batch_id=f"packet06-governed-truth-{eval_id}",
            eval_id=eval_id,
            execution_mode="multistep_batchable",
        )
        run_batch(
            batch_spec=batch_spec,
            eval_cards={eval_id: eval_cards[eval_id]},
            model_route_override=LocalStubModelClient.create(response_text="done").route,
        )
        batch_dir = tmp_path / batch_spec["batch_id"]
        record = _result_records(batch_dir)[0]
        trace = _trace_summaries(batch_dir)[0]
        assert record["governed_terminal_status"] in {"tool_eval_completed", "tool_eval_incomplete"}
        assert record["governed_terminal_status"] != "not_applicable"
        assert record["forced_probe_observed"] is False
        assert trace["governed_eval_truth"]["completion_scope"] == "case_coverage_only"
        assert trace["governed_eval_truth"]["authority_completeness"] in {"complete", "incomplete"}


def test_openai_api_provider_route_forces_api_key_route_override_for_pd_eval():
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_internal_discovery_evidence_efficiency_v1"
    route = {
        "execution_mode": "multistep_batchable",
        "model_tier_policy": eval_cards[eval_id]["model_tier_policy"],
        "eval_card": eval_cards[eval_id],
    }
    batch_model_policy = {
        "screening_default": "oauth:gpt-5.4-mini",
        "screening_fallback": "oauth:gpt-5.4-mini",
        "promotion_tier": "gpt-5.3-codex",
    }

    override = _resolve_batch_model_route_override(
        route=route,
        batch_model_policy=batch_model_policy,
        batch_model_route_override=None,
        model_tier_selector="screening_default",
        batch_provider_route="openai_api",
    )

    assert override is not None
    assert override["provider_route"] == "openai_api"
    assert override["auth_mode"] == "api_key"
    assert override["model_name"] == "gpt-5.4-mini"
    assert override["request_settings"]["api_key_env_var"] == "OPENAI_API_KEY"


def test_openai_api_provider_route_preserves_azure_api_key_route_override_for_pd_eval(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example-resource.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    monkeypatch.setenv("AZURE_OPENAI_GPT54_MINI_KEY", "secret-mini-key")
    monkeypatch.setenv("AZURE_OPENAI_GPT54_MINI_DEPLOYMENT", "dep-gpt54-mini")
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_internal_multifile_repair_test_verify_v1"
    route = {
        "execution_mode": "multistep_batchable",
        "model_tier_policy": eval_cards[eval_id]["model_tier_policy"],
        "eval_card": eval_cards[eval_id],
    }
    batch_model_policy = {
        "screening_default": "azure:gpt-5.4-mini",
        "screening_fallback": "azure:gpt-5.4-mini",
        "promotion_tier": "azure:gpt-5.3-codex",
    }

    override = _resolve_batch_model_route_override(
        route=route,
        batch_model_policy=batch_model_policy,
        batch_model_route_override=None,
        model_tier_selector="screening_default",
        batch_provider_route="openai_api",
    )

    assert override is not None
    assert override["provider_route"] == "openai_api"
    assert override["auth_mode"] == "api_key"
    assert override["model_client_id"] == "azure_openai_api_key"
    assert override["request_settings"]["api_key_env_var"] == "AZURE_OPENAI_GPT54_MINI_KEY"
    assert override["request_settings"]["pricing_model_id"] == "gpt-5.4-mini"


def test_internal_discovery_evidence_efficiency_v1_runtime_path(tmp_path):
    eval_id = "ae_internal_discovery_evidence_efficiency_v1"
    eval_cards = _load_active_eval_cards()
    fixture_plan = materialize_packet03_eval_fixture(
        route={"eval_id": eval_id, "eval_card": eval_cards[eval_id]},
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "internal_discovery_regime_alpha",
            "task_prompt": "inspect evidence bundle then write the report",
            "rerun_index": 0,
            "claim_route_id": "cr_v04_tb_01",
            "task_intent": "tool_call_classification_task_shaped",
        },
        run_dir=tmp_path / "packet05b-internal-discovery-runtime-path",
    )
    fixture = fixture_plan["fixture"]
    run_dir = Path(fixture_plan["fixture_ref"]).resolve().parent
    evidence_text = (run_dir / fixture["evidence_bundle_path"]).read_text(encoding="utf-8")
    report_path = run_dir / fixture["report_path"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(evidence_text, encoding="utf-8")
    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 1,
            "status": "tool_executed",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": "ls workspace/internal_discovery/evidence && cat workspace/internal_discovery/evidence/evidence_bundle.json",
                    "exit_code": 0,
                    "stdout": "ok\n",
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 9, "output_tokens": 6}},
        },
        {
            "step": 1,
            "tool_calls": 1,
            "status": "tool_executed",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": "cp workspace/internal_discovery/evidence/evidence_bundle.json workspace/internal_discovery/output/classification_report.json",
                    "exit_code": 0,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 8, "output_tokens": 5}},
        }
    ]
    execution_result["execution"]["step_count"] = 2
    graded = apply_packet03_eval_grader(
        route={"eval_id": eval_id, "eval_card": eval_cards[eval_id]},
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    summary = graded["packet03_eval_trace"]

    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "pass"
    assert summary["mechanism_visibility_complete"] is True
    assert summary["schema_complete_for_promotion"] is True
    assert summary["bounded_probing_markers"]["within_budget"] is True
    assert summary["final_justification_markers"]["present"] is True
    assert summary["final_justification_markers"]["canonical"] is True
    assert summary["call_class_telemetry"]["valid_dict_case"] == "valid_call"
    assert summary["attribution_case_results"]["mixed_fault_live_case"] == "runtime_error"
    assert summary["assistant_completion_trace"]["step_count"] == 0


def test_internal_multifile_repair_test_verify_v1_runtime_path(tmp_path):
    eval_id = "ae_internal_multifile_repair_test_verify_v1"
    eval_cards = _load_active_eval_cards()
    fixture_plan = materialize_packet03_eval_fixture(
        route={"eval_id": eval_id, "eval_card": eval_cards[eval_id]},
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "internal_multifile_regime_alpha",
            "task_prompt": "inspect, repair two files, verify, then complete",
            "rerun_index": 0,
            "claim_route_id": "cr_v04_vc_01",
            "task_intent": "verify_before_completion_task_shaped",
        },
        run_dir=tmp_path / "packet05b-internal-multifile-runtime-path",
    )
    fixture = fixture_plan["fixture"]
    run_dir = Path(fixture_plan["fixture_ref"]).resolve().parent
    for relative_path, expected_text in fixture["expected_file_texts"].items():
        if relative_path.endswith("settings.backup.env"):
            continue
        path = run_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected_text, encoding="utf-8")
    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 1,
            "status": "tool_executed",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": "cat workspace/internal_multifile/evidence/patch_plan.json && cat workspace/internal_multifile/src/service.py && cat workspace/internal_multifile/config/settings.env",
                    "exit_code": 0,
                    "stdout": "ok\n",
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 9, "output_tokens": 6}},
        },
        {
            "step": 1,
            "tool_calls": 1,
            "status": "tool_executed",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": "printf \"MODE = 'repair_ready'\\n\" > workspace/internal_multifile/src/service.py && printf \"ENABLE_VERIFICATION=true\\n\" > workspace/internal_multifile/config/settings.env && python3 workspace/internal_multifile/tools/verify_changes.py",
                    "exit_code": 0,
                    "stdout": "VERIFIED\n",
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 8, "output_tokens": 5}},
        }
    ]
    execution_result["execution"]["step_count"] = 2
    graded = apply_packet03_eval_grader(
        route={"eval_id": eval_id, "eval_card": eval_cards[eval_id]},
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    summary = graded["packet03_eval_trace"]

    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "pass"
    assert summary["mechanism_visibility_complete"] is True
    assert summary["verify_before_completion"] is True
    assert summary["verifier_execution_seen"] is True
    assert summary["all_targets_written_before_verifier"] is True
    assert all(summary["inspect_before_edit_markers"].values())
    assert summary["assistant_completion_trace"]["step_count"] == 0
    assert set(summary["final_evidence_packet"]["changed_files"]) == {
        "workspace/internal_multifile/config/settings.env",
        "workspace/internal_multifile/src/service.py",
    }


def test_internal_multifile_repair_test_verify_v1_detects_inline_python_writes(tmp_path):
    eval_id = "ae_internal_multifile_repair_test_verify_v1"
    eval_cards = _load_active_eval_cards()
    fixture_plan = materialize_packet03_eval_fixture(
        route={"eval_id": eval_id, "eval_card": eval_cards[eval_id]},
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "internal_multifile_inline_python_writes",
            "task_prompt": "inspect then repair both files and verify",
            "rerun_index": 0,
            "claim_route_id": "probe_pd02_runtime_admission",
            "task_intent": "project_owned_multifile_probe",
        },
        run_dir=tmp_path / "packet05b-internal-multifile-inline-python-writes",
    )
    fixture = fixture_plan["fixture"]
    service_path, config_path = fixture["target_paths"]
    verifier_path = fixture["verifier_path"]
    run_dir = Path(fixture_plan["fixture_ref"]).resolve().parent
    for relative_path, expected_text in fixture["expected_file_texts"].items():
        if relative_path.endswith("settings.backup.env"):
            continue
        path = run_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected_text, encoding="utf-8")
    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 1,
            "status": "tool_executed",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": (
                        f"cat {service_path} && cat {config_path} && "
                        "cat workspace/internal_multifile/evidence/patch_plan.json"
                    ),
                    "exit_code": 0,
                    "stdout": "ok\n",
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 9, "output_tokens": 6}},
        },
        {
            "step": 1,
            "tool_calls": 1,
            "status": "tool_executed",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": (
                        "python3 - <<'PY'\n"
                        "from pathlib import Path\n"
                        f"Path('{service_path}').write_text(\"MODE = 'repair_ready'\\n\")\n"
                        f"Path('{config_path}').write_text('ENABLE_VERIFICATION=true\\n')\n"
                        "PY\n"
                        f"python3 {verifier_path}"
                    ),
                    "exit_code": 0,
                    "stdout": "VERIFIED\n",
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 8, "output_tokens": 5}},
        },
    ]
    execution_result["execution"]["step_count"] = 2
    graded = apply_packet03_eval_grader(
        route={"eval_id": eval_id, "eval_card": eval_cards[eval_id]},
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    summary = graded["packet03_eval_trace"]

    assert summary["all_targets_written_before_verifier"] is True
    assert all(summary["inspect_before_edit_markers"].values())
    assert summary["verifier_execution_seen"] is True


def test_internal_discovery_justification_reason_codes_split_missing_vs_noncanonical(tmp_path):
    eval_id = "ae_internal_discovery_evidence_efficiency_v1"
    eval_cards = _load_active_eval_cards()
    fixture_plan = materialize_packet03_eval_fixture(
        route={"eval_id": eval_id, "eval_card": eval_cards[eval_id]},
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "internal_discovery_reason_code_split",
            "task_prompt": "inspect evidence bundle then write the report",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "packet05b-internal-discovery-reason-code-split",
    )
    fixture = fixture_plan["fixture"]
    run_dir = Path(fixture_plan["fixture_ref"]).resolve().parent
    report_path = run_dir / fixture["report_path"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    expected_report = dict(fixture["expected_report"])

    execution_result_missing = _seed_execution_result(eval_id)
    execution_result_missing["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 1,
            "status": "tool_executed",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": "cat workspace/internal_discovery/evidence/evidence_bundle.json",
                    "exit_code": 0,
                    "stdout": "ok\n",
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 6, "output_tokens": 4}},
        },
        {
            "step": 1,
            "tool_calls": 1,
            "status": "tool_executed",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": "cp workspace/internal_discovery/evidence/evidence_bundle.json workspace/internal_discovery/output/classification_report.json",
                    "exit_code": 0,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 5, "output_tokens": 4}},
        },
    ]
    execution_result_missing["execution"]["step_count"] = 2
    report_missing = dict(expected_report)
    report_missing.pop("justification", None)
    report_path.write_text(json.dumps(report_missing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    graded_missing = apply_packet03_eval_grader(
        route={"eval_id": eval_id, "eval_card": eval_cards[eval_id]},
        execution_result=execution_result_missing,
        fixture_plan=fixture_plan,
    )
    missing_codes = graded_missing["score_envelope"]["layers"]["L2_replay_or_state_grader"]["reason_codes"]
    assert "internal_discovery_justification_absent" in missing_codes
    assert "internal_discovery_justification_noncanonical" not in missing_codes

    execution_result_noncanonical = _seed_execution_result(eval_id)
    execution_result_noncanonical["execution"]["steps"] = execution_result_missing["execution"]["steps"]
    execution_result_noncanonical["execution"]["step_count"] = 2
    report_noncanonical = dict(expected_report)
    report_noncanonical["justification"] = "decoy_only"
    report_path.write_text(json.dumps(report_noncanonical, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    graded_noncanonical = apply_packet03_eval_grader(
        route={"eval_id": eval_id, "eval_card": eval_cards[eval_id]},
        execution_result=execution_result_noncanonical,
        fixture_plan=fixture_plan,
    )
    noncanonical_codes = graded_noncanonical["score_envelope"]["layers"]["L2_replay_or_state_grader"]["reason_codes"]
    assert "internal_discovery_justification_noncanonical" in noncanonical_codes
    assert "internal_discovery_justification_absent" not in noncanonical_codes


def test_tool_result_probe_distinguishes_missing_runtime_category_as_fail(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_tool_result_normalization_permission_probe"
    route = {"eval_id": eval_id, "eval_card": eval_cards[eval_id]}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "task-001",
            "task_prompt": "semantic probe",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "tool-result-missing-category",
    )
    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 1,
            "status": "forced_runtime_probe",
            "results": [
                {
                    "tool_name": "raw_bash",
                    "command": "echo ok",
                    "exit_code": 0,
                    "stdout": "ok\n",
                    "stderr": "",
                    "timed_out": False,
                }
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 0, "output_tokens": 0}},
        }
    ]
    execution_result["execution"]["step_count"] = 1
    graded = apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "fail"
    assert (
        "tool_result_permission_runtime_not_separable"
        in graded["score_envelope"]["layers"]["L2_replay_or_state_grader"]["reason_codes"]
    )


def test_tool_result_attribution_v2_fails_closed_on_incomplete_attribution_trace(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_tool_result_attribution_quality_v2"
    route = {"eval_id": eval_id, "eval_card": eval_cards[eval_id]}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "tool_result_live_cases",
            "task_prompt": "semantic probe",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "tool-result-attribution-incomplete-trace",
    )
    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": 4,
            "status": "forced_runtime_probe",
            "results": [
                {
                    "case_id": "permission_live_case",
                    "result_class": "permission_denied",
                    "reason_code": "tool_permission_denied",
                    "attribution_trace": {"permission_signal_detected": True, "runtime_signal_detected": False},
                },
                {
                    "case_id": "runtime_live_case",
                    "result_class": "runtime_error",
                    "reason_code": "tool_runtime_nonzero_exit",
                    "attribution_trace": {"permission_signal_detected": False, "runtime_signal_detected": True},
                },
                {
                    "case_id": "mixed_fault_live_case",
                    "result_class": "runtime_error",
                    "reason_code": "tool_runtime_mixed_permission_runtime_signals",
                    "attribution_trace": {"permission_signal_detected": True, "runtime_signal_detected": False},
                },
                {
                    "case_id": "success_live_case",
                    "result_class": "success",
                    "reason_code": "tool_success",
                    "attribution_trace": {"permission_signal_detected": False, "runtime_signal_detected": False},
                },
            ],
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 0, "output_tokens": 0}},
        }
    ]
    execution_result["execution"]["step_count"] = 1
    graded = apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    trace = graded["packet03_eval_trace"]
    reason_codes = set(graded["score_envelope"]["layers"]["L2_replay_or_state_grader"]["reason_codes"])
    assert graded["score_envelope"]["aggregate"]["final_verdict"] == "fail"
    assert trace["mechanism_visibility_complete"] is False
    assert trace["schema_complete_for_promotion"] is False
    assert "mixed_fault_live_case" in trace["tool_result_attribution_incomplete_case_ids"]
    assert "tool_result_attribution_evidence_incomplete" in reason_codes


def test_tool_family_trace_separates_raw_vs_governed_truth_for_deterministic_reruns(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_tool_call_contract_quality_v2"
    batch_spec = _single_eval_batch_spec(
        tmp_path=tmp_path,
        batch_id="packet05a-tool-truth-separation",
        eval_id=eval_id,
        execution_mode="deterministic_no_model",
    )

    run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: eval_cards[eval_id]},
    )

    batch_dir = tmp_path / batch_spec["batch_id"]
    record = _result_records(batch_dir)[0]
    trace = _trace_summaries(batch_dir)[0]
    run_events_path = batch_dir / record["run_artifact_refs"]["run_events_ref"]
    events = [json.loads(line) for line in run_events_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert trace["raw_execution_truth"]["execution_status"] == "max_steps_exhausted"
    assert trace["governed_eval_truth"]["governed_terminal_status"] == "tool_eval_completed"
    assert trace["governed_eval_truth"]["final_verdict"] == record["score_summary"]["final_verdict"]
    assert trace["governed_eval_truth"]["completion_scope"] == "case_coverage_only"
    assert trace["governed_eval_truth"]["authority_completeness"] == "incomplete"
    assert "governed_final_verdict_not_pass" in trace["governed_eval_truth"]["authority_incomplete_reasons"]
    assert record["governed_terminal_status"] == "tool_eval_completed"
    assert record["promotion_eligibility"].startswith("blocked_")
    assert "lane_policy_restriction" in record["promotion_blocker_codes"]
    assert "governed_eval_truth_finalized" in record["governed_truth_ref"]

    pre_governance_events = [event for event in events if event["event_type"] == "score_envelope_ready"]
    assert pre_governance_events
    pre_governance_details = pre_governance_events[-1]["payload"]["details"]
    assert pre_governance_details["truth_scope"] == "pre_governance_score_envelope"
    assert pre_governance_details["is_governed_final_truth"] is False
    assert "final_verdict" not in pre_governance_details
    assert pre_governance_details["score_envelope_verdict"] == "fail"

    governed_events = [event for event in events if event["event_type"] == "governed_eval_truth_finalized"]
    assert governed_events
    governed_details = governed_events[-1]["payload"]["details"]
    assert governed_details["raw_execution_truth"]["execution_status"] == "max_steps_exhausted"
    assert governed_details["governed_eval_truth"]["governed_terminal_status"] == "tool_eval_completed"
    assert governed_details["governed_eval_truth"]["authority_completeness"] == "incomplete"


def test_sync_recovery_probe_uses_forced_path_with_bounded_l3(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_sync_interrupt_cleanup_probe"
    batch_spec = _single_eval_batch_spec(
        tmp_path=tmp_path,
        batch_id="packet03-sync-semantic",
        eval_id=eval_id,
        execution_mode="sync_interactive",
    )

    run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: eval_cards[eval_id]},
        model_route_override=LocalStubModelClient.create(response_text="done").route,
    )

    batch_dir = tmp_path / batch_spec["batch_id"]
    record = _result_records(batch_dir)[0]
    trace = _trace_summaries(batch_dir)[0]
    score = _score_envelope_for_record(batch_dir, record)
    assert record["score_summary"]["final_verdict"] == "pass"
    assert record["failure_cluster"] == "none"
    assert record["promotion_eligibility"] == "blocked_bounded_diagnostic_lane"
    assert "bounded_l3_dependency" in record["promotion_blocker_codes"]
    assert score["layers"]["L0_inline_assertion"]["status"] == "pass"
    assert score["layers"]["L2_replay_or_state_grader"]["status"] == "pass"
    assert score["layers"]["L3_judge_layer"]["status"] == "pass"
    assert score["layers"]["L3_judge_layer"]["judge_config"]["mode"] == "bounded_diagnostic_human_gated"
    assert "sync_interrupt_probe_bounded_without_l3" not in record["reason_codes"]
    assert "pinned_l3_judge_not_implemented_packet03" not in record["reason_codes"]
    assert trace["packet03_eval_summary"]["forced_path_probe_defined"] is True
    assert trace["packet03_eval_summary"]["runtime_probe_executed"] is True
    assert trace["packet03_eval_summary"]["interrupt_observed"] is True
    assert trace["packet03_eval_summary"]["cleanup_observed"] is True
    assert trace["packet03_eval_summary"]["l3_judge_contract_configured"] is True
    assert trace["packet03_eval_summary"]["l3_judge_status"] == "pass"


def test_sync_recovery_probe_is_unresolved_when_l3_contract_missing(tmp_path):
    eval_cards = _load_active_eval_cards()
    eval_id = "ae_sync_interrupt_cleanup_probe"
    route = {"eval_id": eval_id, "eval_card": eval_cards[eval_id]}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": "sc_b_01",
            "task_id": "task-001",
            "task_prompt": "semantic probe",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "sync-interrupt-no-l3-contract",
    )
    fixture_plan["fixture"].pop("l3_judge_contract", None)
    execution_result = _seed_execution_result(eval_id)
    execution_result["execution"]["runtime_probe"] = {
        "executed_call_count": 2,
        "interrupt_observed": True,
        "cleanup_observed": True,
    }
    execution_result["run_events"] = [{"phase": "recover", "event_type": "cleanup_completed"}]

    graded = apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    score = graded["score_envelope"]
    reason_codes = set(score["layers"]["L3_judge_layer"]["reason_codes"])

    assert score["aggregate"]["final_verdict"] == "unresolved"
    assert score["layers"]["L2_replay_or_state_grader"]["status"] == "pass"
    assert score["layers"]["L3_judge_layer"]["status"] == "unavailable"
    assert "sync_interrupt_l3_judge_contract_missing" in reason_codes
    assert "required_layer_missing_l3_judge_layer" in reason_codes
    assert "sync_interrupt_l3_contract_unavailable" in score["layers"]["L4_final_acceptance"]["reason_codes"]


def test_reference_baseline_is_bounded_in_packet03_recommendations():
    recommendation = _build_recommendation_draft(
        {
            "batch_id": "packet03-recommendation-boundary",
            "variant_ids": ["sc_b_01"],
            "fixed_invariants": {"comparator_variant_id": "sc_b_01"},
        },
        [
            {
                "variant_id": "sc_b_01",
                "run_id": "run-001",
                "score_summary": {"final_verdict": "pass"},
                "budget_used": {"estimated_tokens": 18},
            }
        ],
    )

    candidate = recommendation["candidate_actions"][0]
    assert candidate["proposed_status"] == "bound"
    assert "cannot self-promote" in candidate["rationale"]


def test_reference_baseline_alias_is_bounded_when_comparator_id_differs():
    recommendation = _build_recommendation_draft(
        {
            "batch_id": "p03_det_atomic_reference_post_guardrepairs_20260419",
            "eval_family": "packet_03_atomic_reference_deterministic",
            "task_set_id": "packet03-det-reference-set",
            "variant_ids": ["sc_b_01"],
            "fixed_invariants": {"comparator_variant_id": "reference_baseline_packet_02"},
        },
        [
            {
                "variant_id": "sc_b_01",
                "run_id": "run-001",
                "score_summary": {"final_verdict": "pass"},
                "budget_used": {"estimated_tokens": 18},
            }
        ],
    )

    candidate = recommendation["candidate_actions"][0]
    assert candidate["proposed_status"] == "bound"
    assert "cannot self-promote" in candidate["rationale"]


def test_unresolved_variant_cannot_promote_in_packet03_recommendations():
    recommendation = _build_recommendation_draft(
        {
            "batch_id": "packet03-candidate-atomic",
            "eval_family": "packet_03_atomic_candidate",
            "task_set_id": "packet03-candidate-set",
            "variant_ids": ["vf_pc_01"],
            "fixed_invariants": {"comparator_variant_id": "reference_baseline_packet_02"},
        },
        [
            {
                "variant_id": "vf_pc_01",
                "run_id": "run-001",
                "score_summary": {"final_verdict": "unresolved"},
                "budget_used": {"estimated_tokens": 18},
            }
        ],
    )

    candidate = recommendation["candidate_actions"][0]
    assert candidate["proposed_status"] == "hold_for_more_evidence"


def test_non_baseline_pass_variant_can_promote_in_packet03_recommendations():
    recommendation = _build_recommendation_draft(
        {
            "batch_id": "packet03-candidate-atomic",
            "eval_family": "packet_03_atomic_candidate",
            "task_set_id": "packet03-candidate-set",
            "variant_ids": ["vf_pc_01"],
            "fixed_invariants": {"comparator_variant_id": "reference_baseline_packet_02"},
        },
        [
            {
                "variant_id": "vf_pc_01",
                "run_id": "run-001",
                "score_summary": {"final_verdict": "pass"},
                "budget_used": {"estimated_tokens": 18},
            },
            {
                "variant_id": "vf_pc_01",
                "run_id": "run-002",
                "score_summary": {"final_verdict": "pass"},
                "budget_used": {"estimated_tokens": 22},
            },
        ],
    )

    candidate = recommendation["candidate_actions"][0]
    assert candidate["proposed_status"] == "promote_to_atomic_eligible"
