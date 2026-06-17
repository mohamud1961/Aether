"""Packet 03 eval-specific fixture materialization for active atomic families."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WORKSPACE_TARGET_LEGACY_EVAL_IDS = frozenset(
    {
        "ae_workspace_target_correctness_probe",
        "eval_workspace_target_correctness_atomic_v1",
    }
)
WORKSPACE_TARGET_REPAIRED_EVAL_IDS = frozenset(
    {
        "ae_workspace_target_decoy_generalization_v2",
        "eval_workspace_target_decoy_generalization_atomic_v2",
    }
)
WORKSPACE_TARGET_MULTISTEP_EVAL_IDS = frozenset(
    {
        "ae_workspace_target_decoy_generalization_multistep_v1",
        "eval_workspace_target_decoy_generalization_multistep_v1",
    }
)

PROMOTION_LANE_DEFAULT_EVAL_IDS = frozenset(
    {
        "ae_cwd_workdir_path_contract_guard",
        "ae_tool_call_shape_argument_contract",
        "ae_tool_call_contract_quality_v2",
        "ae_tool_result_attribution_quality_v2",
        "ae_verification_reason_code_quality_v2",
        "ae_lifecycle_adversarial_terminality_v2",
        "ae_internal_discovery_evidence_efficiency_v1",
        "ae_internal_multifile_repair_test_verify_v1",
        "ae_internal_toolchain_dependency_pressure_v1",
        "ae_internal_artifact_log_extraction_v1",
    }
)
GUARDRAIL_DEBUG_EVAL_IDS = frozenset(
    {
        "ae_completion_layer_contract_guard",
        "ae_lifecycle_terminality_contract_guard",
        *WORKSPACE_TARGET_REPAIRED_EVAL_IDS,
        *WORKSPACE_TARGET_MULTISTEP_EVAL_IDS,
    }
)
FORCED_PROBE_GUARDRAIL_EVAL_IDS = frozenset(
    {
        *WORKSPACE_TARGET_LEGACY_EVAL_IDS,
        "ae_tool_result_normalization_permission_probe",
    }
)
BOUNDED_L3_GUARDRAIL_EVAL_IDS = frozenset(
    {
        "ae_sync_interrupt_cleanup_probe",
    }
)
BOUNDED_DIAGNOSTIC_EVAL_IDS = frozenset(
    {
        "ae_completion_verifier_final_contradiction_probe",
    }
)

PACKET03_EVAL_LANE_POLICY: dict[str, dict[str, Any]] = {
    eval_id: {
        "default_evaluation_lane": "promotion",
        "promotion_blocker_codes": [],
    }
    for eval_id in PROMOTION_LANE_DEFAULT_EVAL_IDS
}
for eval_id in FORCED_PROBE_GUARDRAIL_EVAL_IDS:
    PACKET03_EVAL_LANE_POLICY[eval_id] = {
        "default_evaluation_lane": "guardrail_debug",
        "promotion_blocker_codes": ["forced_probe_dependency"],
    }
for eval_id in GUARDRAIL_DEBUG_EVAL_IDS:
    PACKET03_EVAL_LANE_POLICY[eval_id] = {
        "default_evaluation_lane": "guardrail_debug",
        "promotion_blocker_codes": [],
    }
for eval_id in BOUNDED_L3_GUARDRAIL_EVAL_IDS:
    PACKET03_EVAL_LANE_POLICY[eval_id] = {
        "default_evaluation_lane": "bounded_diagnostic",
        "promotion_blocker_codes": ["bounded_l3_dependency"],
    }
for eval_id in BOUNDED_DIAGNOSTIC_EVAL_IDS:
    PACKET03_EVAL_LANE_POLICY[eval_id] = {
        "default_evaluation_lane": "bounded_diagnostic",
        "promotion_blocker_codes": [],
    }


def get_packet03_eval_lane_policy(eval_id: str) -> dict[str, Any]:
    policy = PACKET03_EVAL_LANE_POLICY.get(eval_id)
    if policy is None:
        raise ValueError(f"Packet 04A lane policy missing for eval_id={eval_id}")
    return {
        "default_evaluation_lane": policy["default_evaluation_lane"],
        "promotion_blocker_codes": list(policy["promotion_blocker_codes"]),
    }


def materialize_packet03_eval_fixture(
    *,
    route: dict[str, Any],
    result_context: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    eval_id = route["eval_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    fixture = _build_fixture(
        eval_id=eval_id,
        route=route,
        result_context=result_context,
        run_dir=run_dir,
    )
    fixture_path = run_dir / "packet03_fixture.json"
    fixture_path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lane_metadata = _build_fixture_lane_metadata(
        eval_id=eval_id,
        route=route,
        fixture=fixture,
    )
    return {
        "eval_id": eval_id,
        "fixture": fixture,
        "fixture_ref": str(fixture_path),
        "task_prompt": fixture.get("task_prompt", result_context["task_prompt"]),
        "task_id": result_context["task_id"],
        "runtime_probe": fixture.get("runtime_probe"),
        "model_client_kwargs": fixture.get("model_client_kwargs"),
        "exercise_activation_contract": fixture.get("exercise_activation_contract"),
        "workspace_state_overrides": fixture.get("workspace_state_overrides"),
        "execution_state_overrides": fixture.get("execution_state_overrides"),
        "lane_metadata": lane_metadata,
    }


def _build_fixture(
    *,
    eval_id: str,
    route: dict[str, Any],
    result_context: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    fixed_invariants = route.get("eval_card", {}).get("fixed_invariants", {})
    grader_id = fixed_invariants.get("grader_version", f"{eval_id}_grader_v1")
    fixture_id = fixed_invariants.get("fixture_version", f"{eval_id}_fixture_v1")
    base = {
        "eval_id": eval_id,
        "fixture_id": fixture_id,
        "grader_id": grader_id,
        "seed_id": result_context["variant_id"],
    }
    claim_route_id = result_context.get("claim_route_id")
    if isinstance(claim_route_id, str) and claim_route_id:
        base["claim_route_id"] = claim_route_id
    task_intent = result_context.get("task_intent")
    if isinstance(task_intent, str) and task_intent:
        base["task_intent"] = task_intent
    if eval_id == "ae_completion_layer_contract_guard":
        return {
            **base,
            "required_layers": [
                "L0_inline_assertion",
                "L1_verifier_artifact",
                "L2_replay_or_state_grader",
                "L4_final_acceptance",
            ],
            "expected_verification": {
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
            "task_prompt": (
                "Packet03 completion-layer fixture: keep explicit lower-layer evidence and "
                "do not substitute L3 for missing L2."
            ),
        }
    if eval_id == "ae_completion_verifier_final_contradiction_probe":
        return {
            **base,
            "requires_pinned_l3_judge": False,
            "contradiction_contract": {
                "contract_id": "p15_deterministic_verifier_final_tuple_v1",
                "expected_contradiction": True,
                "verifier_positive_layer": "L1_verifier_artifact",
                "final_acceptance_layer": "L4_final_acceptance",
            },
            "l3_judge_contract": {
                "judge_type": "deterministic_local_contradiction_contract_v1",
                "model": "local_deterministic_contract",
                "prompt_fingerprint": "p15_contradiction_tuple_prompt_v1",
                "schema_fingerprint": "p15_contradiction_tuple_schema_v1",
                "mode": "phase15_measurement_repair",
            },
            "workspace_state_overrides": {
                "model_claimed_done": False,
                "layer_statuses": {
                    "L0_inline_assertion": "pass",
                    "L1_verifier_artifact": "pass",
                    "L2_replay_or_state_grader": "pass",
                    "L4_final_acceptance": "fail",
                },
            },
            "task_prompt": (
                "Phase15 contradiction fixture: preserve verifier/final outputs for deterministic "
                "verifier-positive versus final-acceptance contradiction judging."
            ),
        }
    if eval_id == "ae_verification_reason_code_quality_v2":
        task_id = result_context["task_id"]
        if task_id == "verification_missing_l1_non_substitution":
            return {
                **base,
                "expected_verification": {
                    "verified": False,
                    "reason_codes": ["layered_acceptance_rejected"],
                    "substitution_violations": ["non_substitution_violation_l4_over_l1_verifier_artifact"],
                    "layer_statuses": {
                        "L0_inline_assertion": "pass",
                        "L1_verifier_artifact": "fail",
                        "L2_replay_or_state_grader": "pass",
                        "L4_final_acceptance": "pass",
                    },
                },
                "workspace_state_overrides": {
                    "model_claimed_done": True,
                    "layer_statuses": {
                        "L0_inline_assertion": "pass",
                        "L1_verifier_artifact": "fail",
                        "L2_replay_or_state_grader": "pass",
                        "L4_final_acceptance": "pass",
                    },
                },
                "task_prompt": (
                    "Packet05A verification quality fixture: final acceptance claims pass while "
                    "L1 is failed. Verification must reject and emit explicit non-substitution telemetry."
                ),
            }
        return {
            **base,
            "expected_verification": {
                "verified": False,
                "reason_codes": ["layered_acceptance_rejected"],
                "substitution_violations": ["non_substitution_violation_l4_over_l2_replay_or_state_grader"],
                "layer_statuses": {
                    "L0_inline_assertion": "pass",
                    "L1_verifier_artifact": "pass",
                    "L2_replay_or_state_grader": "fail",
                    "L4_final_acceptance": "pass",
                },
            },
            "workspace_state_overrides": {
                "model_claimed_done": True,
                "layer_statuses": {
                    "L0_inline_assertion": "pass",
                    "L1_verifier_artifact": "pass",
                    "L2_replay_or_state_grader": "fail",
                    "L4_final_acceptance": "pass",
                },
            },
            "task_prompt": (
                "Packet05A verification quality fixture: final acceptance claims pass while "
                "L2 is failed. Verification must reject and emit explicit replay-layer non-substitution telemetry."
            ),
        }
    if eval_id == "ae_tool_call_shape_argument_contract":
        tool_call_matrix = [
            {
                "case_id": "valid_dict_command",
                "tool_call": {"name": "raw_bash", "arguments": {"command": "echo packet03"}},
                "expected_class": "valid_call",
            },
            {
                "case_id": "valid_json_command",
                "tool_call": {"name": "raw_bash", "arguments": "{\"command\": \"pwd\"}"},
                "expected_class": "valid_call",
            },
            {
                "case_id": "missing_command",
                "tool_call": {"name": "raw_bash", "arguments": {}},
                "expected_class": "malformed_call",
            },
            {
                "case_id": "unknown_tool",
                "tool_call": {"name": "unknown_tool", "arguments": {"command": "pwd"}},
                "expected_class": "unsupported_tool",
            },
            {
                "case_id": "empty_arguments",
                "tool_call": {"name": "raw_bash", "arguments": ""},
                "expected_class": "malformed_call",
            },
        ]
        return {
            **base,
            "tool_call_matrix": tool_call_matrix,
            "runtime_probe": {
                "probe_id": "p03_tool_call_shape_runtime_v1",
                "forced_tool_calls": [
                    {
                        "label": row["case_id"],
                        "case_id": row["case_id"],
                        "expected_class": row["expected_class"],
                        "phase": "tool",
                        "event_type": "tool_call_shape_probe_step",
                        "tool_call": row["tool_call"],
                    }
                    for row in tool_call_matrix
                ],
            },
            "task_prompt": "Packet03 tool-call fixture: enforce raw_bash argument-contract shape.",
        }
    if eval_id == "ae_lifecycle_terminality_contract_guard":
        return {
            **base,
            "terminality_tuple": {
                "expected_terminal_state": "completed",
                "allowed_terminal_states": ["completed", "error", "max_steps_exhausted"],
                "terminal_state_flags": {
                    "completed": True,
                    "error": False,
                    "max_steps_exhausted": False,
                },
                "bounded_loop": {"step_bound_max": 1},
                "terminal_artifact_state": {"status": "single_terminal_write", "write_count": 1},
                "cleanup_state": {"required": True, "status": "completed"},
            },
            "task_prompt": (
                "Packet03 lifecycle fixture: enforce bounded loop terminality, single terminal "
                "state, and cleanup completion tuple coherence."
            ),
        }
    if eval_id == "ae_lifecycle_adversarial_terminality_v2":
        task_id = result_context["task_id"]
        if task_id == "lifecycle_duplicate_terminal_write_attempt":
            return {
                **base,
                "adversarial_case_id": task_id,
                "expected_lifecycle": {
                    "expected_final_status": "completed",
                    "expected_reason_codes": ["lifecycle_terminal_write_count_invalid"],
                    "expected_duplicate_terminal_write": True,
                    "expected_cleanup_race_detected": False,
                    "expected_post_cancel_tool_return_count": 0,
                },
                "execution_state_overrides": {
                    "terminal_write_attempt_count": 2,
                    "terminal_write_count": 1,
                    "lifecycle_sequence_fingerprint": (
                        "loop_entered>terminal_outcome_written>"
                        "terminal_outcome_duplicate_blocked>cleanup_started>cleanup_completed>loop_exited"
                    ),
                    "cleanup_completion_reason_codes": ["loop_cleanup_completed"],
                    "cleanup_completed": True,
                    "cleanup_race_detected": False,
                    "unresolved_state_exit_count": 0,
                    "runtime_probe": {
                        "defined": True,
                        "planned_call_count": 0,
                        "executed_call_count": 0,
                        "interrupt_observed": False,
                        "cleanup_observed": True,
                        "observed_event_types": [],
                        "tool_results": [],
                    },
                },
                "task_prompt": (
                    "Packet05A lifecycle adversarial fixture: detect duplicate terminal-write "
                    "attempts without collapsing the run into a false clean lifecycle."
                ),
            }
        if task_id == "lifecycle_post_cancel_tool_return":
            return {
                **base,
                "adversarial_case_id": task_id,
                "expected_lifecycle": {
                    "expected_final_status": "completed",
                    "expected_reason_codes": ["lifecycle_post_cancel_tool_return_observed"],
                    "expected_duplicate_terminal_write": False,
                    "expected_cleanup_race_detected": False,
                    "expected_post_cancel_tool_return_count": 1,
                },
                "execution_state_overrides": {
                    "runtime_probe": {
                        "defined": True,
                        "planned_call_count": 2,
                        "executed_call_count": 2,
                        "interrupt_observed": True,
                        "cleanup_observed": True,
                        "post_cancel_tool_return_count": 1,
                        "observed_event_types": [
                            "lifecycle_interrupt_boundary",
                            "lifecycle_post_cancel_return",
                        ],
                        "tool_results": [],
                    },
                    "cleanup_completion_reason_codes": ["loop_cleanup_completed"],
                    "cleanup_completed": True,
                    "cleanup_race_detected": False,
                },
                "task_prompt": (
                    "Packet05A lifecycle adversarial fixture: preserve explicit delayed-return-"
                    "after-cancel evidence when cleanup still completes."
                ),
            }
        return {
            **base,
            "adversarial_case_id": task_id,
            "expected_lifecycle": {
                "expected_final_status": "error",
                "expected_reason_codes": ["lifecycle_interrupt_cleanup_missing"],
                "expected_duplicate_terminal_write": False,
                "expected_cleanup_race_detected": True,
                "expected_post_cancel_tool_return_count": 0,
            },
            "execution_state_overrides": {
                "runtime_probe": {
                    "defined": True,
                    "planned_call_count": 1,
                    "executed_call_count": 1,
                    "interrupt_observed": True,
                    "cleanup_observed": False,
                    "post_cancel_tool_return_count": 0,
                    "observed_event_types": ["lifecycle_interrupt_boundary"],
                    "tool_results": [],
                },
                "cleanup_completion_reason_codes": [],
                "cleanup_completed": False,
                "cleanup_race_detected": True,
            },
            "task_prompt": (
                "Packet05A lifecycle adversarial fixture: detect incomplete cleanup after "
                "interrupt pressure and downgrade the terminal state."
            ),
        }
    if eval_id == "ae_cwd_workdir_path_contract_guard":
        target_file = run_dir / "workspace" / "target" / "packet03_path_probe.txt"
        _write_text(target_file, "packet03_path_probe\n")
        normalized_target = str(target_file.resolve())
        cwd = str(run_dir.resolve())
        return {
            **base,
            "path_contract_tuple": {
                "target_cwd": cwd,
                "recorded_cwd": cwd,
                "recorded_workdir": cwd,
                "resolved_target_path": normalized_target,
                "normalized_target_path": normalized_target,
                "path_metadata_complete": True,
            },
            "task_prompt": (
                "Packet03 cwd/workdir fixture: keep cwd/workdir/path metadata coherent and "
                "grounded to the deterministic target path."
            ),
        }
    if eval_id in WORKSPACE_TARGET_LEGACY_EVAL_IDS:
        target_path = "workspace/target/answer.txt"
        target_backup_path = "workspace/target/answer_backup.txt"
        decoy_path = "workspace/decoy/answer.txt"
        target_initial_text = "packet03_target_initial\n"
        target_expected_text = "packet03_target_updated\n"
        target_expected_token = "packet03_target_updated"
        decoy_backup_text = "packet03_decoy_backup_initial\n"
        decoy_other_text = "packet03_decoy_other_initial\n"
        _write_text(run_dir / target_path, target_initial_text)
        _write_text(run_dir / target_backup_path, decoy_backup_text)
        _write_text(run_dir / decoy_path, decoy_other_text)
        return {
            **base,
            "target_path": target_path,
            "decoy_paths": [
                target_backup_path,
                decoy_path,
            ],
            "target_initial_text": target_initial_text,
            "target_expected_text": target_expected_text,
            "decoy_expected_texts": {
                target_backup_path: decoy_backup_text,
                decoy_path: decoy_other_text,
            },
            "runtime_probe": {
                "probe_id": "p03_workspace_target_probe_runtime_v1",
                "forced_tool_calls": [
                    {
                        "label": "write_target_only",
                        "phase": "tool",
                        "event_type": "workspace_target_probe_step",
                        "tool_call": {
                            "name": "raw_bash",
                            "arguments": {
                                "command": f"printf '{target_expected_token}\\n' > {target_path}",
                            },
                        },
                    }
                ],
            },
            "task_prompt": (
                "Edit only workspace/target/answer.txt. Ignore decoys: "
                "workspace/target/answer_backup.txt and workspace/decoy/answer.txt."
            ),
        }
    if eval_id in WORKSPACE_TARGET_REPAIRED_EVAL_IDS:
        return _build_workspace_target_decoy_generalization_fixture(
            base=base,
            result_context=result_context,
            run_dir=run_dir,
        )
    if eval_id in WORKSPACE_TARGET_MULTISTEP_EVAL_IDS:
        return _build_workspace_target_decoy_multistep_fixture(
            base=base,
            result_context=result_context,
            run_dir=run_dir,
        )
    if eval_id == "ae_tool_result_normalization_permission_probe":
        return {
            **base,
            "classification_matrix": [
                {
                    "case_id": "deny_case",
                    "result_payload": {"exit_code": 126, "stderr": "Permission denied by policy"},
                    "expected_class": "permission_denied",
                },
                {
                    "case_id": "runtime_case",
                    "result_payload": {"exit_code": 127, "stderr": "command not found"},
                    "expected_class": "runtime_error",
                },
                {
                    "case_id": "success_case",
                    "result_payload": {"exit_code": 0, "stdout": "ok"},
                    "expected_class": "success",
                },
            ],
            "required_runtime_categories": ["permission_denied", "runtime_error"],
            "runtime_probe": {
                "probe_id": "p03_tool_result_normalization_runtime_v1",
                "forced_tool_calls": [
                    {
                        "label": "permission_denied_case",
                        "phase": "tool",
                        "event_type": "tool_result_probe_step",
                        "tool_call": {
                            "name": "raw_bash",
                            "arguments": {
                                "command": "printf 'Permission denied by policy\\n' >&2; exit 126",
                            },
                        },
                    },
                    {
                        "label": "runtime_error_case",
                        "phase": "tool",
                        "event_type": "tool_result_probe_step",
                        "tool_call": {
                            "name": "raw_bash",
                            "arguments": {"command": "packet03_missing_command_for_probe"},
                        },
                    },
                    {
                        "label": "success_case",
                        "phase": "tool",
                        "event_type": "tool_result_probe_step",
                        "tool_call": {
                            "name": "raw_bash",
                            "arguments": {"command": "echo packet03_tool_probe_ok"},
                        },
                    },
                ],
            },
            "task_prompt": (
                "Run tool outputs through normalization and keep permission-denied separate "
                "from runtime errors."
            ),
        }
    if eval_id == "ae_tool_result_attribution_quality_v2":
        planned_calls = [
            {
                "name": "raw_bash",
                "case_id": "permission_live_case",
                "arguments": {"command": "printf 'Permission denied by policy\\n' >&2; exit 126"},
            },
            {
                "name": "raw_bash",
                "case_id": "runtime_live_case",
                "arguments": {"command": "printf 'No such file or directory\\n' >&2; exit 1"},
            },
            {
                "name": "raw_bash",
                "case_id": "mixed_fault_live_case",
                "arguments": {
                    "command": "printf 'Permission denied\\nNo such file or directory\\n' >&2; exit 1",
                },
            },
            {
                "name": "raw_bash",
                "case_id": "success_live_case",
                "arguments": {"command": "printf 'packet05a_tool_ok\\n'"},
            },
        ]
        return {
            **base,
            "expected_attribution_cases": [
                {
                    "case_id": "permission_live_case",
                    "expected_result_class": "permission_denied",
                    "expected_reason_code": "tool_permission_denied",
                },
                {
                    "case_id": "runtime_live_case",
                    "expected_result_class": "runtime_error",
                    "expected_reason_code": "tool_runtime_nonzero_exit",
                },
                {
                    "case_id": "mixed_fault_live_case",
                    "expected_result_class": "runtime_error",
                    "expected_reason_code": "tool_runtime_mixed_permission_runtime_signals",
                },
                {
                    "case_id": "success_live_case",
                    "expected_result_class": "success",
                    "expected_reason_code": "tool_success",
                },
            ],
            "model_client_kwargs": {
                "planned_completions": [
                    {
                        "text": "",
                        "tool_calls": planned_calls,
                    }
                ]
            },
            "task_prompt": (
            "Packet05A tool-result attribution fixture: execute live deny/runtime/mixed/success "
            "cases through the normal tool path and preserve exact attribution telemetry."
        ),
    }
    if eval_id == "ae_internal_discovery_evidence_efficiency_v1":
        return _build_internal_discovery_evidence_efficiency_fixture(
            base=base,
            run_dir=run_dir,
        )
    if eval_id == "ae_internal_multifile_repair_test_verify_v1":
        return _build_internal_multifile_repair_test_verify_fixture(
            base=base,
            run_dir=run_dir,
        )
    if eval_id == "ae_internal_toolchain_dependency_pressure_v1":
        return _build_internal_toolchain_dependency_pressure_fixture(
            base=base,
        )
    if eval_id == "ae_internal_artifact_log_extraction_v1":
        return _build_internal_artifact_log_extraction_fixture(
            base=base,
        )
    if eval_id == "ae_tool_call_contract_quality_v2":
        planned_calls = [
            {
                "name": "raw_bash",
                "case_id": "valid_dict_case",
                "arguments": {"command": "printf 'packet05a_tool_contract_ok\\n'"},
            },
            {
                "name": "raw_bash",
                "case_id": "valid_json_string_case",
                "arguments": "{\"command\": \"printf 'packet05a_json_ok\\\\n'\"}",
            },
            {
                "name": "raw_bash",
                "case_id": "plain_string_arguments_case",
                "arguments": "printf 'plain string should be rejected\\n'",
            },
            {
                "name": "raw_bash",
                "case_id": "malformed_json_string_case",
                "arguments": "{\"command\":",
            },
            {
                "name": "raw_bash",
                "case_id": "missing_command_case",
                "arguments": {"cmd": "printf 'missing command\\n'"},
            },
        ]
        return {
            **base,
            "expected_tool_call_cases": [
                {
                    "case_id": "valid_dict_case",
                    "expected_contract_class": "valid_call",
                    "expected_result_class": "success",
                    "expected_reason_code": "tool_success",
                },
                {
                    "case_id": "valid_json_string_case",
                    "expected_contract_class": "valid_call",
                    "expected_result_class": "success",
                    "expected_reason_code": "tool_success",
                },
                {
                    "case_id": "plain_string_arguments_case",
                    "expected_contract_class": "malformed_call",
                    "expected_result_class": "contract_error",
                    "expected_reason_code": "tool_call_contract_malformed",
                },
                {
                    "case_id": "malformed_json_string_case",
                    "expected_contract_class": "malformed_call",
                    "expected_result_class": "contract_error",
                    "expected_reason_code": "tool_call_contract_malformed",
                },
                {
                    "case_id": "missing_command_case",
                    "expected_contract_class": "malformed_call",
                    "expected_result_class": "contract_error",
                    "expected_reason_code": "tool_call_contract_malformed",
                },
            ],
            "model_client_kwargs": {
                "planned_completions": [
                    {
                        "text": "",
                        "tool_calls": planned_calls,
                    }
                ]
            },
            "task_prompt": (
                "Packet05A tool-call contract fixture: execute valid, malformed, unsupported, "
                "and camouflage argument cases through the normal tool path and preserve exact "
                "contract classification telemetry."
            ),
        }
    if eval_id == "ae_sync_interrupt_cleanup_probe":
        cleanup_marker_path = "workspace/runtime/sync_cleanup.marker"
        _write_text(run_dir / cleanup_marker_path, "pending\n")
        return {
            **base,
            "requires_pinned_l3_judge": True,
            "l3_judge_contract": {
                "judge_type": "bounded_sync_interrupt_recovery_judge_v1",
                "model": "packet03_sync_interrupt_l3_pinned_v1",
                "prompt_fingerprint": "p03_sync_interrupt_l3_prompt_v1",
                "schema_fingerprint": "p03_sync_interrupt_l3_schema_v1",
                "mode": "bounded_diagnostic_human_gated",
            },
            "forced_path_probe": [
                {"phase": "execute", "event": "interrupt_requested"},
                {"phase": "recover", "event": "cleanup_completed"},
            ],
            "cleanup_marker_path": cleanup_marker_path,
            "cleanup_expected_text": "packet03_cleanup_completed\n",
            "runtime_probe": {
                "probe_id": "p03_sync_interrupt_cleanup_runtime_v1",
                "forced_tool_calls": [
                    {
                        "label": "interrupt_boundary",
                        "phase": "execute",
                        "event_type": "interrupt_requested",
                        "tool_call": {
                            "name": "raw_bash",
                            "arguments": {
                                "command": "printf 'packet03 interrupt boundary\\n' >&2; exit 2",
                            },
                        },
                    },
                    {
                        "label": "cleanup_step",
                        "phase": "recover",
                        "event_type": "cleanup_completed",
                        "tool_call": {
                            "name": "raw_bash",
                            "arguments": {
                                "command": f"printf 'packet03_cleanup_completed\\n' > {cleanup_marker_path}",
                            },
                        },
                    },
                ],
            },
            "task_prompt": (
                "Exercise interruption and cleanup. Recovery evidence must show bounded resume "
                "and cleanup completion."
            ),
        }
    return {
        **base,
        "task_prompt": result_context["task_prompt"],
    }


def _build_internal_discovery_evidence_efficiency_fixture(
    *,
    base: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    root = run_dir / "workspace" / "internal_discovery"
    evidence_path = root / "evidence" / "evidence_bundle.json"
    report_path = root / "output" / "classification_report.json"
    decoy_path = root / "decoy" / "misleading_bundle.json"
    evidence_bundle = {
        "tool_contract_cases": {
            "plain_string_arguments_case": "malformed_call",
            "valid_dict_case": "valid_call",
        },
        "tool_result_cases": {
            "mixed_fault_live_case": "runtime_error",
            "permission_live_case": "permission_denied",
        },
        "justification": "evidence_bundle_inspected",
    }
    _write_text(evidence_path, json.dumps(evidence_bundle, indent=2, sort_keys=True) + "\n")
    _write_text(
        decoy_path,
        json.dumps(
            {
                "tool_contract_cases": {"valid_dict_case": "malformed_call"},
                "tool_result_cases": {"mixed_fault_live_case": "permission_denied"},
                "justification": "decoy_only",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return {
        **base,
        "fixture_family": "packet05b_project_owned_internal_discovery",
        "workspace_root": str(root),
        "evidence_bundle_path": str(evidence_path.relative_to(run_dir)),
        "report_path": str(report_path.relative_to(run_dir)),
        "required_report_keys": [
            "tool_contract_cases",
            "tool_result_cases",
            "justification",
        ],
        "required_justification_value": "evidence_bundle_inspected",
        "decoy_paths": [str(decoy_path.relative_to(run_dir))],
        "expected_report": evidence_bundle,
        "probe_budget_max": 4,
        "task_prompt": (
            "Packet05B internal discovery/evidence task. Inspect the evidence bundle in the workspace, "
            f"then write JSON to {report_path.relative_to(run_dir)}. "
            "classification_report.json must include exactly these top-level keys: "
            "tool_contract_cases, tool_result_cases, justification. "
            "justification must be the canonical value evidence_bundle_inspected. "
            "Read real evidence before writing, keep probing bounded, and do not touch decoy files."
        ),
    }


def _build_internal_multifile_repair_test_verify_fixture(
    *,
    base: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    root = run_dir / "workspace" / "internal_multifile"
    source_a = root / "src" / "service.py"
    source_b = root / "config" / "settings.env"
    decoy_path = root / "config" / "settings.backup.env"
    verifier_path = root / "tools" / "verify_changes.py"
    patch_plan_path = root / "evidence" / "patch_plan.json"
    expected_service = "MODE = 'repair_ready'\n"
    expected_settings = "ENABLE_VERIFICATION=true\n"
    _write_text(source_a, "MODE = 'stale'\n")
    _write_text(source_b, "ENABLE_VERIFICATION=false\n")
    _write_text(decoy_path, "ENABLE_VERIFICATION=backup_only\n")
    patch_plan = {
        "targets": [
            {
                "path": str(source_a.relative_to(run_dir)),
                "expected_text": expected_service,
            },
            {
                "path": str(source_b.relative_to(run_dir)),
                "expected_text": expected_settings,
            },
        ],
        "verifier_path": str(verifier_path.relative_to(run_dir)),
    }
    _write_text(patch_plan_path, json.dumps(patch_plan, indent=2, sort_keys=True) + "\n")
    _write_text(
        verifier_path,
        "\n".join(
            [
                "from pathlib import Path",
                "",
                "service = Path('workspace/internal_multifile/src/service.py').read_text(encoding='utf-8')",
                "settings = Path('workspace/internal_multifile/config/settings.env').read_text(encoding='utf-8')",
                "if service != \"MODE = 'repair_ready'\\n\":",
                "    raise SystemExit(1)",
                "if settings != 'ENABLE_VERIFICATION=true\\n':",
                "    raise SystemExit(1)",
                "print('VERIFIED')",
            ]
        )
        + "\n",
    )
    return {
        **base,
        "fixture_family": "packet05b_project_owned_internal_multifile",
        "workspace_root": str(root),
        "patch_plan_path": str(patch_plan_path.relative_to(run_dir)),
        "verifier_path": str(verifier_path.relative_to(run_dir)),
        "target_paths": [
            str(source_a.relative_to(run_dir)),
            str(source_b.relative_to(run_dir)),
        ],
        "decoy_paths": [str(decoy_path.relative_to(run_dir))],
        "expected_file_texts": {
            str(source_a.relative_to(run_dir)): expected_service,
            str(source_b.relative_to(run_dir)): expected_settings,
            str(decoy_path.relative_to(run_dir)): "ENABLE_VERIFICATION=backup_only\n",
        },
        "task_prompt": (
            "Packet05B internal multi-file repair task. Inspect the exact patch plan file "
            "workspace/internal_multifile/evidence/patch_plan.json and both required target files first: "
            "workspace/internal_multifile/src/service.py and workspace/internal_multifile/config/settings.env. "
            "Apply the exact two-file repair and ensure both edits are complete before executing "
            "workspace/internal_multifile/tools/verify_changes.py. Do not touch the backup decoy."
        ),
    }


def _build_internal_toolchain_dependency_pressure_fixture(
    *,
    base: dict[str, Any],
) -> dict[str, Any]:
    expected_cases = [
        {
            "case_id": "valid_dict_case",
            "expected_contract_class": "valid_call",
            "expected_result_class": "success",
            "expected_reason_code": "tool_success",
        },
        {
            "case_id": "plain_string_arguments_case",
            "expected_contract_class": "malformed_call",
            "expected_result_class": "contract_error",
            "expected_reason_code": "tool_call_contract_malformed",
        },
        {
            "case_id": "malformed_json_string_case",
            "expected_contract_class": "malformed_call",
            "expected_result_class": "contract_error",
            "expected_reason_code": "tool_call_contract_malformed",
        },
    ]
    case_matrix_calls = [
        {
            "label": "toolchain_valid_dict",
            "phase": "tool",
            "event_type": "toolchain_probe_step",
            "case_id": "valid_dict_case",
            "tool_call": {
                "name": "raw_bash",
                "case_id": "valid_dict_case",
                "arguments": {"command": "printf 'toolchain_probe_ok\\n'"},
            },
        },
        {
            "label": "toolchain_plain_string",
            "phase": "tool",
            "event_type": "toolchain_probe_step",
            "case_id": "plain_string_arguments_case",
            "tool_call": {
                "name": "raw_bash",
                "case_id": "plain_string_arguments_case",
                "arguments": "printf 'plain string should be rejected\\n'",
            },
        },
        {
            "label": "toolchain_malformed_json",
            "phase": "tool",
            "event_type": "toolchain_probe_step",
            "case_id": "malformed_json_string_case",
            "tool_call": {
                "name": "raw_bash",
                "case_id": "malformed_json_string_case",
                "arguments": "{\"command\":",
            },
        },
    ]
    return {
        **base,
        "fixture_family": "packet06_toolchain_dependency_pressure",
        "expected_toolchain_cases": expected_cases,
        "runtime_probe": {
            "probe_id": "p06_toolchain_dependency_pressure_runtime_v1",
            "probe_mode": "case_matrix_live_v1",
            "contamination_safe": True,
            "case_matrix_tool_calls": case_matrix_calls,
        },
        "task_prompt": (
            "Packet06 non-proxy corroboration: pressure tool invocation contract handling under "
            "dependency-style malformed argument load and preserve explicit case telemetry."
        ),
    }


def _build_internal_artifact_log_extraction_fixture(
    *,
    base: dict[str, Any],
) -> dict[str, Any]:
    expected_cases = [
        {
            "case_id": "permission_live_case",
            "expected_result_class": "permission_denied",
            "expected_reason_code": "tool_permission_denied",
        },
        {
            "case_id": "mixed_fault_live_case",
            "expected_result_class": "runtime_error",
            "expected_reason_code": "tool_runtime_mixed_permission_runtime_signals",
        },
        {
            "case_id": "success_live_case",
            "expected_result_class": "success",
            "expected_reason_code": "tool_success",
        },
    ]
    case_matrix_calls = [
        {
            "label": "artifact_permission_case",
            "phase": "tool",
            "event_type": "artifact_log_probe_step",
            "case_id": "permission_live_case",
            "tool_call": {
                "name": "raw_bash",
                "case_id": "permission_live_case",
                "arguments": {"command": "printf 'Permission denied by policy\\n' >&2; exit 126"},
            },
        },
        {
            "label": "artifact_mixed_fault_case",
            "phase": "tool",
            "event_type": "artifact_log_probe_step",
            "case_id": "mixed_fault_live_case",
            "tool_call": {
                "name": "raw_bash",
                "case_id": "mixed_fault_live_case",
                "arguments": {
                    "command": "printf 'Permission denied\\nNo such file or directory\\n' >&2; exit 1",
                },
            },
        },
        {
            "label": "artifact_success_case",
            "phase": "tool",
            "event_type": "artifact_log_probe_step",
            "case_id": "success_live_case",
            "tool_call": {
                "name": "raw_bash",
                "case_id": "success_live_case",
                "arguments": {"command": "printf 'artifact_log_probe_ok\\n'"},
            },
        },
    ]
    return {
        **base,
        "fixture_family": "packet06_artifact_log_extraction",
        "expected_artifact_log_cases": expected_cases,
        "runtime_probe": {
            "probe_id": "p06_artifact_log_extraction_runtime_v1",
            "probe_mode": "case_matrix_live_v1",
            "contamination_safe": True,
            "case_matrix_tool_calls": case_matrix_calls,
        },
        "task_prompt": (
            "Packet06 non-proxy corroboration: extract artifact/log signal quality across "
            "permission, mixed-fault, and success outcomes with explicit attribution traces."
        ),
    }


def _build_workspace_target_decoy_generalization_fixture(
    *,
    base: dict[str, Any],
    result_context: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    regime = _select_workspace_target_decoy_regime(result_context=result_context)
    target = regime["target"]
    decoys = regime["decoys"]
    _write_text(run_dir / target["path"], target["initial_text"])
    _write_text(run_dir / target["payload_source_path"], target["expected_text"])
    for decoy in decoys:
        _write_text(run_dir / decoy["path"], decoy["initial_text"])
    decoy_ids = ", ".join(decoy["decoy_id"] for decoy in decoys)
    decoy_paths = ", ".join(decoy["path"] for decoy in decoys)
    payload_source_path = target["payload_source_path"]
    payload_copy_example = f"cat {payload_source_path} > {target['path']}"
    return {
        **base,
        "surface_alias": "eval_workspace_target_decoy_generalization_atomic_v2",
        "regime_id": regime["regime_id"],
        "regime_rotation_index": regime["rotation_index"],
        "regime_count": regime["regime_count"],
        "target_descriptor": {
            "target_id": target["target_id"],
            "path": target["path"],
            "expected_text": target["expected_text"],
        },
        "activation_payload_descriptor": {
            "payload_id": target["payload_id"],
            "source_path": payload_source_path,
            "copy_command_example": payload_copy_example,
            "expected_text_disclosed_in_prompt": False,
        },
        "decoy_descriptors": [
            {
                "decoy_id": decoy["decoy_id"],
                "path": decoy["path"],
                "expected_text": decoy["initial_text"],
            }
            for decoy in decoys
        ],
        "target_expected_text": target["expected_text"],
        "decoy_expected_texts": {
            decoy["path"]: decoy["initial_text"]
            for decoy in decoys
        },
        "development_transfer_framing": {
            "task_tier": "development_transfer",
            "framing_mode": "first_honest_reentry",
            "frozen_invariants": [
                "target_decoy_ids_are_explicit",
                "regime_rotation_declared",
                "forced_probe_satisfier_forbidden",
            ],
        },
        "visibility_contract": {
            "require_target_decoy_ids": True,
            "require_target_and_decoy_touch_evidence": True,
            "fail_closed_on_incomplete_visibility": True,
            "forbid_forced_probe_satisfier": True,
        },
        "exercise_activation_contract": {
            "require_live_tool_call": True,
            "preferred_tool_name": "raw_bash",
            "first_turn_tool_only_response": True,
            "require_payload_copy_from_source": True,
            "forbid_forced_probe_satisfier": True,
            "fail_closed_reason_code": "workspace_target_decoy_generalization_not_exercised_no_tool_calls",
        },
        "task_prompt": (
            "Development-transfer workspace-target task. Edit only "
            f"{target['target_id']} at {target['path']}. "
            f"Do not touch decoys ({decoy_ids}) at {decoy_paths}. "
            f"Activation payload source is {payload_source_path}. "
            "First response contract: emit exactly one raw_bash tool call and no prose. "
            f"Copy the payload from {payload_source_path} into {target['path']} exactly "
            f"(example command: {payload_copy_example}). "
            "Do not paraphrase or restate payload text in assistant prose. "
            "Plain-text/no-tool responses are scored as not exercised. "
            "Show mechanism-visible target grounding under this rotated decoy regime."
        ),
    }


def _build_workspace_target_decoy_multistep_fixture(
    *,
    base: dict[str, Any],
    result_context: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    fixture = _build_workspace_target_decoy_generalization_fixture(
        base=base,
        result_context=result_context,
        run_dir=run_dir,
    )
    target = fixture["target_descriptor"]
    activation_payload = fixture["activation_payload_descriptor"]
    source_path = activation_payload["source_path"]
    target_path = target["path"]
    fixture["surface_alias"] = "eval_workspace_target_decoy_generalization_multistep_v1"
    fixture["multistep_turn_contract"] = {
        "minimum_turn_count": 2,
        "require_first_turn_tool_observation": True,
        "require_post_observation_step": True,
        "require_target_touch_after_observation": True,
    }
    fixture["exercise_activation_contract"] = {
        "require_live_tool_call": True,
        "preferred_tool_name": "raw_bash",
        "first_turn_tool_only_response": True,
        "require_payload_observation_first": True,
        "require_payload_copy_from_source": True,
        "require_second_turn_decision_or_edit": True,
        "activation_payload_source_path": source_path,
        "retry_tool_call_command_hint": f"cat {source_path}",
        "suppress_first_no_tool_assistant_history": True,
        "forbid_forced_probe_satisfier": True,
        "fail_closed_reason_code": "workspace_target_multistep_turn_contract_not_satisfied",
    }
    fixture["task_prompt"] = (
        "Development-transfer workspace-target multistep task. "
        f"Turn 1 must observe payload source {source_path} with exactly one raw_bash tool call and no prose. "
        f"Turn 2 must use the observed payload to update target {target_path}; do not touch decoys. "
        "Do not disclose payload text in assistant prose. "
        "Runs that skip the observation->post-observation turn structure are fail-closed."
    )
    return fixture


def _select_workspace_target_decoy_regime(*, result_context: dict[str, Any]) -> dict[str, Any]:
    regimes = [
        {
            "regime_id": "decoy_rotation_alpha",
            "target": {
                "target_id": "target_alpha_primary",
                "path": "workspace/dev_transfer_alpha/target/answer.txt",
                "payload_id": "target_alpha_activation_payload",
                "payload_source_path": "workspace/dev_transfer_alpha/target/activation_payload.txt",
                "initial_text": "alpha_target_initial\n",
                "expected_text": "alpha_target_updated\n",
            },
            "decoys": [
                {
                    "decoy_id": "decoy_alpha_neighbor",
                    "path": "workspace/dev_transfer_alpha/decoy/answer.txt",
                    "initial_text": "alpha_decoy_neighbor_initial\n",
                },
                {
                    "decoy_id": "decoy_alpha_shadow",
                    "path": "workspace/dev_transfer_alpha/target/answer_shadow.txt",
                    "initial_text": "alpha_decoy_shadow_initial\n",
                },
            ],
        },
        {
            "regime_id": "decoy_rotation_beta",
            "target": {
                "target_id": "target_beta_primary",
                "path": "workspace/dev_transfer_beta/release/final_answer.md",
                "payload_id": "target_beta_activation_payload",
                "payload_source_path": "workspace/dev_transfer_beta/release/activation_payload.txt",
                "initial_text": "beta_target_initial\n",
                "expected_text": "beta_target_updated\n",
            },
            "decoys": [
                {
                    "decoy_id": "decoy_beta_neighbor",
                    "path": "workspace/dev_transfer_beta/release/final_answer_backup.md",
                    "initial_text": "beta_decoy_neighbor_initial\n",
                },
                {
                    "decoy_id": "decoy_beta_parallel",
                    "path": "workspace/dev_transfer_beta/decoy/final_answer.md",
                    "initial_text": "beta_decoy_parallel_initial\n",
                },
            ],
        },
    ]
    task_id = result_context.get("task_id")
    if isinstance(task_id, str):
        lowered_task_id = task_id.lower()
        if "regime_alpha" in lowered_task_id:
            index = 0
        elif "regime_beta" in lowered_task_id:
            index = 1
        else:
            index = _coerce_non_negative_int(result_context.get("rerun_index")) % len(regimes)
    else:
        index = _coerce_non_negative_int(result_context.get("rerun_index")) % len(regimes)
    selected = dict(regimes[index])
    selected["rotation_index"] = index
    selected["regime_count"] = len(regimes)
    return selected


def _coerce_non_negative_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(value, 0)
    return 0


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture_lane_metadata(
    *,
    eval_id: str,
    route: dict[str, Any],
    fixture: dict[str, Any],
) -> dict[str, Any]:
    policy = get_packet03_eval_lane_policy(eval_id)
    route_blockers = route.get("lane_blocker_codes", [])
    route_blockers = route_blockers if isinstance(route_blockers, list) else []
    fixture_blockers = _fixture_promotion_blocker_codes(fixture)
    blocker_codes = sorted(
        {
            code
            for code in [*policy["promotion_blocker_codes"], *route_blockers, *fixture_blockers]
            if isinstance(code, str) and code
        }
    )
    evaluation_lane = route.get("evaluation_lane", policy["default_evaluation_lane"])
    return {
        "evaluation_lane": evaluation_lane,
        "promotion_authority": bool(route.get("promotion_authority", evaluation_lane == "promotion")),
        "promotion_blocker_codes": blocker_codes,
        "forced_probe_dependency": "forced_probe_dependency" in blocker_codes,
        "bounded_l3_dependency": "bounded_l3_dependency" in blocker_codes,
    }


def _fixture_promotion_blocker_codes(fixture: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    runtime_probe = fixture.get("runtime_probe")
    if isinstance(runtime_probe, dict):
        forced_calls = runtime_probe.get("forced_tool_calls")
        if isinstance(forced_calls, list) and forced_calls:
            blockers.append("forced_probe_dependency")
    forced_path_probe = fixture.get("forced_path_probe")
    if isinstance(forced_path_probe, list) and forced_path_probe:
        blockers.append("forced_probe_dependency")
    if bool(fixture.get("requires_pinned_l3_judge")):
        blockers.append("bounded_l3_dependency")
    return blockers
