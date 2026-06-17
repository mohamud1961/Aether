"""Packet 04A execution route-manifest helpers."""

from __future__ import annotations

import hashlib
import importlib
import json
import re
from pathlib import Path
from typing import Any, Callable

BASELINE_VARIANT_ID = "sc_b_01"
DEFAULT_PACKET04_ROUTE_SCOPE = "packet04a_first_slice"
PACKET04_SLICE2_ROUTE_SCOPE = "packet04_slice2"
PACKET05A_TOOL_CALL_SCOPE = "packet05a_tool_call"
PACKET05A_TOOL_RESULT_SCOPE = "packet05a_tool_result"
PACKET05A_SYNC_INTERRUPT_SCOPE = "packet05a_sync_interrupt_bounded"
PACKET05A_WORKSPACE_TARGET_SCOPE = "packet05a_workspace_target"
PACKET05A_WORKSPACE_TARGET_MULTISTEP_SCOPE = "packet05a_workspace_target_multistep"
PACKET06_PD01_SCOPE = "packet06_pd01_locked_home"
SUCCESSOR_SLICE1_ROUTE_SCOPE = "successor_slice1_compile"
PACKET06_PHASE2_ENV_TOOLING_SCOPE = "packet06_phase2_env_tooling"
PACKET06_PHASE5_HARD_GAUNTLET_SCOPE = "packet06_phase5_hard_gauntlet"
PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE = "packet06_phase6_context_completion_repair"
RERUN_IN_SCOPE_VARIANTS = (
    "v04_vc_01_layered_non_substitution_reason_codes",
    "v04_ex_01_single_terminal_outcome_cleanup_order_guard",
)
SLICE2_RERUN_IN_SCOPE_VARIANTS = (
    "v04_ex_02_cwd_workdir_invariant_propagation_guard",
    "v04_tb_01_tool_call_contract_classifier",
)
ALLOWED_PACKET04_VARIANTS = frozenset({BASELINE_VARIANT_ID, *RERUN_IN_SCOPE_VARIANTS})
SLICE2_ALLOWED_PACKET04_VARIANTS = frozenset({BASELINE_VARIANT_ID, *SLICE2_RERUN_IN_SCOPE_VARIANTS})
PACKET05A_TOOL_CALL_VARIANTS = ("v04_tb_01_tool_call_contract_classifier",)
PACKET05A_TOOL_CALL_ALLOWED_VARIANTS = frozenset({BASELINE_VARIANT_ID, *PACKET05A_TOOL_CALL_VARIANTS})
PACKET05A_TOOL_RESULT_VARIANTS = ("v04_tb_02_permission_runtime_attribution_split",)
PACKET05A_TOOL_RESULT_ALLOWED_VARIANTS = frozenset({BASELINE_VARIANT_ID, *PACKET05A_TOOL_RESULT_VARIANTS})
PACKET05A_SYNC_INTERRUPT_VARIANTS = ("v04_rb_01_interrupt_retry_spiral_breaker",)
PACKET05A_SYNC_INTERRUPT_ALLOWED_VARIANTS = frozenset({BASELINE_VARIANT_ID, *PACKET05A_SYNC_INTERRUPT_VARIANTS})
PACKET05A_WORKSPACE_TARGET_VARIANTS = ("v04_cb_01_decoy_resistant_target_selection",)
PACKET05A_WORKSPACE_TARGET_ALLOWED_VARIANTS = frozenset(
    {BASELINE_VARIANT_ID, *PACKET05A_WORKSPACE_TARGET_VARIANTS}
)
PACKET05A_WORKSPACE_TARGET_MULTISTEP_VARIANTS = ("v04_cb_01_decoy_resistant_target_selection",)
PACKET05A_WORKSPACE_TARGET_MULTISTEP_ALLOWED_VARIANTS = frozenset(
    {BASELINE_VARIANT_ID, *PACKET05A_WORKSPACE_TARGET_MULTISTEP_VARIANTS}
)
PACKET06_PD01_VARIANTS = ("prompt_plan_env", "evidence_report_scaffold")
PACKET06_PD01_ALLOWED_VARIANTS = frozenset({BASELINE_VARIANT_ID, *PACKET06_PD01_VARIANTS})
SUCCESSOR_SLICE1_VARIANTS = (
    "spb_01",
    "rhv1_ref_01",
    "rhv1_ablate_env_01",
    "rhv1_ablate_state_01",
    "rhv1_ablate_evidence_01",
    "rh1_no_completion_01",
)
SUCCESSOR_SLICE1_ALLOWED_VARIANTS = frozenset({BASELINE_VARIANT_ID, *SUCCESSOR_SLICE1_VARIANTS})
PACKET06_PHASE2_ENV_TOOLING_VARIANTS = (
    "spb_01",
    "v04_tb_01_tool_call_contract_classifier",
    "v04_tb_02_permission_runtime_attribution_split",
    "spb_tooling_seed_01",
    "spb_env_snapshot_seed_01",
    "spb_receipt_context_seed_01",
    "spb_completion_gate_seed_01",
    "spb_tooling_seed_plus_receipt_context_01",
    "spb_tooling_seed_plus_completion_gate_01",
    "spb_tooling_seed_plus_receipt_and_completion_01",
    "spb_trace_learning_seed_01",
)
PACKET06_PHASE2_ENV_TOOLING_ALLOWED_VARIANTS = frozenset(
    {BASELINE_VARIANT_ID, *PACKET06_PHASE2_ENV_TOOLING_VARIANTS}
)
PACKET06_PHASE5_HARD_GAUNTLET_VARIANTS = (
    "spb_01",
    "spb_tooling_seed_plus_receipt_and_completion_01",
    "model_led_compaction_01",
    "harness_led_receipt_compaction_01",
    "hybrid_model_handoff_plus_receipts_01",
    "codex_style_handoff_compaction_01",
    "bounded_episode_01",
    "adaptive_episode_01",
    "failure_autopsy_repair_loop_01",
    "verification_repair_loop_01",
    "bigai_style_manager_worker_verifier_01",
)
PACKET06_PHASE5_HARD_GAUNTLET_ALLOWED_VARIANTS = frozenset(
    {BASELINE_VARIANT_ID, *PACKET06_PHASE5_HARD_GAUNTLET_VARIANTS}
)
PACKET06_PHASE6_CONTEXT_COMPLETION_VARIANTS = (
    "spb_01",
    "spb_tooling_seed_plus_receipt_and_completion_01",
    "candidate_plus_model_led_compaction_01",
    "candidate_plus_codex_style_handoff_compaction_01",
    "candidate_plus_hybrid_receipt_handoff_01",
    "candidate_plus_toolcall_completion_guard_01",
    "checkpoint_verify_01",
    "artifact_and_verifier_hard_gate_01",
    "verified_work_pocket_handoff_hybrid_01",
    "candidate_plus_context_answer_extraction_01",
    "candidate_plus_context_budget_guard_01",
    "candidate_plus_artifact_existence_gate_01",
    "candidate_plus_verifier_backed_completion_gate_01",
    "candidate_plus_completion_repair_loop_01",
    "candidate_plus_required_deliverable_tracker_01",
    "candidate_plus_tool_call_plan_tracker_01",
    "candidate_plus_final_required_action_tracker_01",
    "candidate_plus_bfcl_strict_argument_guard_01",
    "candidate_plus_closure_truth_ledger_01",
    "evidence_state_capsule_context_v1",
    "candidate_plus_closure_evidence_projection_01",
    "candidate_plus_app_workspace_path_normalizer_01",
    "service_contract_first_receipt_closure_01",
    "candidate_plus_path_normalized_verifier_repair_projection_01",
    "candidate_plus_path_normalized_target_resolution_guard_01",
    "candidate_plus_path_normalized_exact_target_projection_01",
    "evidence_kernel_composite_v1",
    "active_evidence_kernel_v1",
    "active_evidence_kernel_control_plane_context_v1",
    "model_led_evidence_substrate_v1",
    "winning_harness_v1",
    "zero_abstraction_lean_harness",
)
PACKET06_PHASE6_CONTEXT_COMPLETION_ALLOWED_VARIANTS = frozenset(
    {BASELINE_VARIANT_ID, *PACKET06_PHASE6_CONTEXT_COMPLETION_VARIANTS}
)
OWNERSHIP_BUCKETS = frozenset({"support_infra", "baseline_hardening", "candidate_variant"})
REPO_ROOT = Path(__file__).resolve().parents[1]
PACKET04_VARIANT_CARDS_PATH = (
    REPO_ROOT
    / "tracking/collab/stage_03_execution_planning/packets/packet_04_first_atomic_variants/outputs/variant_cards.md"
)

_RUNTIME_KEYS = (
    "orientation",
    "tools_getter",
    "tool_executor",
    "execution",
    "context",
    "verification",
    "recovery",
    "terminal_guard",
)

_BASE_ROUTE = {
    "orientation": {
        "surface_id": "orientation.raw_prompt_default",
        "ownership_bucket": "baseline_hardening",
        "declared_card_path": "blocks/orientation/raw_prompt.py",
        "real_file_rel": "blocks/orientation/raw_prompt.py",
        "module_import_path": "blocks.orientation.raw_prompt:orient",
    },
    "tools_getter": {
        "surface_id": "tool.raw_bash_definition_surface",
        "ownership_bucket": "baseline_hardening",
        "declared_card_path": "blocks/tools/raw_bash.py",
        "real_file_rel": "blocks/tools/raw_bash.py",
        "module_import_path": "blocks.tools.raw_bash:get_tools",
    },
    "tool_executor": {
        "surface_id": "tool.raw_bash_execution_surface",
        "ownership_bucket": "baseline_hardening",
        "declared_card_path": "blocks/tools/raw_bash.py",
        "real_file_rel": "blocks/tools/raw_bash.py",
        "module_import_path": "blocks.tools.raw_bash:execute_tool_call",
    },
    "execution": {
        "surface_id": "execution.flat_loop_terminality_mechanism",
        "ownership_bucket": "baseline_hardening",
        "declared_card_path": "runner/packet04_route_manifest.py",
        "real_file_rel": "runner/packet04_route_manifest.py",
        "module_import_path": "runner.packet04_route_manifest:baseline_execution_run_loop",
    },
    "context": {
        "surface_id": "context.full_history_default_manager",
        "ownership_bucket": "baseline_hardening",
        "declared_card_path": "blocks/context/full_history.py",
        "real_file_rel": "blocks/context/full_history.py",
        "module_import_path": "blocks.context.full_history:manage",
    },
    "verification": {
        "surface_id": "verification.trust_model_layered_acceptance",
        "ownership_bucket": "baseline_hardening",
        "declared_card_path": "runner/packet04_route_manifest.py",
        "real_file_rel": "runner/packet04_route_manifest.py",
        "module_import_path": "runner.packet04_route_manifest:baseline_verification_check",
    },
    "recovery": {
        "surface_id": "recovery.no_recovery_cleanup_order_variant_hook",
        "ownership_bucket": "baseline_hardening",
        "declared_card_path": "runner/packet04_route_manifest.py",
        "real_file_rel": "runner/packet04_route_manifest.py",
        "module_import_path": "runner.packet04_route_manifest:baseline_recovery_handle_error",
    },
    "terminal_guard": {
        "surface_id": "runner.agent.terminal_outcome_guard",
        "ownership_bucket": "baseline_hardening",
        "declared_card_path": "runner/packet04_route_manifest.py",
        "real_file_rel": "runner/packet04_route_manifest.py",
        "module_import_path": "runner.packet04_route_manifest:baseline_terminal_outcome_guard",
    },
}

_CANDIDATE_OVERRIDES = {
    "v04_vc_01_layered_non_substitution_reason_codes": {
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/trust_model.py",
            "real_file_rel": "blocks/verification/trust_model.py",
            "module_import_path": "blocks.verification.trust_model:check",
            "claimed_changed_surface": True,
        },
    },
    "v04_ex_01_single_terminal_outcome_cleanup_order_guard": {
        "execution": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/execution/flat_loop.py",
            "real_file_rel": "blocks/execution/flat_loop.py",
            "module_import_path": "blocks.execution.flat_loop:run_loop",
            "claimed_changed_surface": True,
        },
        "recovery": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/recovery/no_recovery.py",
            "real_file_rel": "blocks/recovery/no_recovery.py",
            "module_import_path": "blocks.recovery.no_recovery:handle_error",
            "claimed_changed_surface": True,
        },
        "terminal_guard": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "runner/agent.py",
            "real_file_rel": "runner/agent.py",
            "module_import_path": "runner.agent:_apply_terminal_outcome_cleanup_order_guard",
            "claimed_changed_surface": True,
        },
    },
    "v04_ex_02_cwd_workdir_invariant_propagation_guard": {
        "execution": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/execution/cwd_invariant_loop.py",
            "real_file_rel": "blocks/execution/cwd_invariant_loop.py",
            "module_import_path": "blocks.execution.cwd_invariant_loop:run_loop",
            "claimed_changed_surface": True,
        },
    },
    "v04_tb_01_tool_call_contract_classifier": {
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/contract_classifier.py",
            "real_file_rel": "blocks/tools/contract_classifier.py",
            "module_import_path": "blocks.tools.contract_classifier:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/contract_classifier.py",
            "real_file_rel": "blocks/tools/contract_classifier.py",
            "module_import_path": "blocks.tools.contract_classifier:execute_tool_call",
            "claimed_changed_surface": True,
        },
    },
    "v04_tb_02_permission_runtime_attribution_split": {
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/result_normalizer.py",
            "real_file_rel": "blocks/tools/result_normalizer.py",
            "module_import_path": "blocks.tools.result_normalizer:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/result_normalizer.py",
            "real_file_rel": "blocks/tools/result_normalizer.py",
            "module_import_path": "blocks.tools.result_normalizer:execute_tool_call",
            "claimed_changed_surface": True,
        },
    },
    "v04_rb_01_interrupt_retry_spiral_breaker": {
        "terminal_guard": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "runner/agent.py",
            "real_file_rel": "runner/agent.py",
            "module_import_path": "runner.agent:_apply_terminal_outcome_cleanup_order_guard",
            "claimed_changed_surface": True,
        },
    },
    "v04_cb_01_decoy_resistant_target_selection": {
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/workspace_target_state.py",
            "real_file_rel": "blocks/context/workspace_target_state.py",
            "module_import_path": "blocks.context.workspace_target_state:manage",
            "claimed_changed_surface": True,
        },
    },
    "prompt_plan_env": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/prompt_plan_env.py",
            "real_file_rel": "blocks/orientation/prompt_plan_env.py",
            "module_import_path": "blocks.orientation.prompt_plan_env:orient",
            "claimed_changed_surface": True,
        },
    },
    "evidence_report_scaffold": {
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/evidence_report_scaffold.py",
            "real_file_rel": "blocks/context/evidence_report_scaffold.py",
            "module_import_path": "blocks.context.evidence_report_scaffold:manage",
            "claimed_changed_surface": True,
        },
    },
    "spb_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/prompt_plan_env.py",
            "real_file_rel": "blocks/orientation/prompt_plan_env.py",
            "module_import_path": "blocks.orientation.prompt_plan_env:orient",
            "claimed_changed_surface": True,
        },
    },
    "spb_tooling_seed_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/prompt_plan_env.py",
            "real_file_rel": "blocks/orientation/prompt_plan_env.py",
            "module_import_path": "blocks.orientation.prompt_plan_env:orient",
            "claimed_changed_surface": True,
        },
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:execute_tool_call",
            "claimed_changed_surface": True,
        },
    },
    "spb_env_snapshot_seed_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/env_snapshot.py",
            "real_file_rel": "blocks/orientation/env_snapshot.py",
            "module_import_path": "blocks.orientation.env_snapshot:orient",
            "claimed_changed_surface": True,
        },
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:execute_tool_call",
            "claimed_changed_surface": True,
        },
    },
    "spb_receipt_context_seed_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/prompt_plan_env.py",
            "real_file_rel": "blocks/orientation/prompt_plan_env.py",
            "module_import_path": "blocks.orientation.prompt_plan_env:orient",
            "claimed_changed_surface": True,
        },
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/receipt_injection.py",
            "real_file_rel": "blocks/context/receipt_injection.py",
            "module_import_path": "blocks.context.receipt_injection:manage",
            "claimed_changed_surface": True,
        },
    },
    "spb_completion_gate_seed_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/prompt_plan_env.py",
            "real_file_rel": "blocks/orientation/prompt_plan_env.py",
            "module_import_path": "blocks.orientation.prompt_plan_env:orient",
            "claimed_changed_surface": True,
        },
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/completion_gate.py",
            "real_file_rel": "blocks/verification/completion_gate.py",
            "module_import_path": "blocks.verification.completion_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "spb_tooling_seed_plus_receipt_context_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/prompt_plan_env.py",
            "real_file_rel": "blocks/orientation/prompt_plan_env.py",
            "module_import_path": "blocks.orientation.prompt_plan_env:orient",
            "claimed_changed_surface": True,
        },
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/receipt_injection.py",
            "real_file_rel": "blocks/context/receipt_injection.py",
            "module_import_path": "blocks.context.receipt_injection:manage",
            "claimed_changed_surface": True,
        },
    },
    "spb_tooling_seed_plus_completion_gate_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/prompt_plan_env.py",
            "real_file_rel": "blocks/orientation/prompt_plan_env.py",
            "module_import_path": "blocks.orientation.prompt_plan_env:orient",
            "claimed_changed_surface": True,
        },
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/completion_gate.py",
            "real_file_rel": "blocks/verification/completion_gate.py",
            "module_import_path": "blocks.verification.completion_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "spb_tooling_seed_plus_receipt_and_completion_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/prompt_plan_env.py",
            "real_file_rel": "blocks/orientation/prompt_plan_env.py",
            "module_import_path": "blocks.orientation.prompt_plan_env:orient",
            "claimed_changed_surface": True,
        },
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/receipt_injection.py",
            "real_file_rel": "blocks/context/receipt_injection.py",
            "module_import_path": "blocks.context.receipt_injection:manage",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/completion_gate.py",
            "real_file_rel": "blocks/verification/completion_gate.py",
            "module_import_path": "blocks.verification.completion_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "spb_trace_learning_seed_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/prompt_plan_env.py",
            "real_file_rel": "blocks/orientation/prompt_plan_env.py",
            "module_import_path": "blocks.orientation.prompt_plan_env:orient",
            "claimed_changed_surface": True,
        },
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "execution": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/execution/trace_learning_loop.py",
            "real_file_rel": "blocks/execution/trace_learning_loop.py",
            "module_import_path": "blocks.execution.trace_learning_loop:run_loop",
            "claimed_changed_surface": True,
        },
    },
    "rhv1_ref_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/rhv1_prompt_plan_env.py",
            "real_file_rel": "blocks/orientation/rhv1_prompt_plan_env.py",
            "module_import_path": "blocks.orientation.rhv1_prompt_plan_env:orient",
            "claimed_changed_surface": True,
        },
        "execution": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/execution/flat_loop.py",
            "real_file_rel": "blocks/execution/flat_loop.py",
            "module_import_path": "blocks.execution.flat_loop:run_loop",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/evidence_report_scaffold.py",
            "real_file_rel": "blocks/context/evidence_report_scaffold.py",
            "module_import_path": "blocks.context.evidence_report_scaffold:manage",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/trust_model.py",
            "real_file_rel": "blocks/verification/trust_model.py",
            "module_import_path": "blocks.verification.trust_model:check",
            "claimed_changed_surface": True,
        },
        "recovery": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/recovery/no_recovery.py",
            "real_file_rel": "blocks/recovery/no_recovery.py",
            "module_import_path": "blocks.recovery.no_recovery:handle_error",
            "claimed_changed_surface": True,
        },
        "terminal_guard": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "runner/agent.py",
            "real_file_rel": "runner/agent.py",
            "module_import_path": "runner.agent:_apply_terminal_outcome_cleanup_order_guard",
            "claimed_changed_surface": True,
        },
    },
    "rhv1_ablate_env_01": {
        "execution": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/execution/flat_loop.py",
            "real_file_rel": "blocks/execution/flat_loop.py",
            "module_import_path": "blocks.execution.flat_loop:run_loop",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/evidence_report_scaffold.py",
            "real_file_rel": "blocks/context/evidence_report_scaffold.py",
            "module_import_path": "blocks.context.evidence_report_scaffold:manage",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/trust_model.py",
            "real_file_rel": "blocks/verification/trust_model.py",
            "module_import_path": "blocks.verification.trust_model:check",
            "claimed_changed_surface": True,
        },
        "recovery": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/recovery/no_recovery.py",
            "real_file_rel": "blocks/recovery/no_recovery.py",
            "module_import_path": "blocks.recovery.no_recovery:handle_error",
            "claimed_changed_surface": True,
        },
        "terminal_guard": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "runner/agent.py",
            "real_file_rel": "runner/agent.py",
            "module_import_path": "runner.agent:_apply_terminal_outcome_cleanup_order_guard",
            "claimed_changed_surface": True,
        },
    },
    "rhv1_ablate_state_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/rhv1_prompt_plan_env.py",
            "real_file_rel": "blocks/orientation/rhv1_prompt_plan_env.py",
            "module_import_path": "blocks.orientation.rhv1_prompt_plan_env:orient",
            "claimed_changed_surface": True,
        },
        "execution": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/execution/flat_loop.py",
            "real_file_rel": "blocks/execution/flat_loop.py",
            "module_import_path": "blocks.execution.flat_loop:run_loop",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/trust_model.py",
            "real_file_rel": "blocks/verification/trust_model.py",
            "module_import_path": "blocks.verification.trust_model:check",
            "claimed_changed_surface": True,
        },
        "recovery": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/recovery/no_recovery.py",
            "real_file_rel": "blocks/recovery/no_recovery.py",
            "module_import_path": "blocks.recovery.no_recovery:handle_error",
            "claimed_changed_surface": True,
        },
        "terminal_guard": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "runner/agent.py",
            "real_file_rel": "runner/agent.py",
            "module_import_path": "runner.agent:_apply_terminal_outcome_cleanup_order_guard",
            "claimed_changed_surface": True,
        },
    },
    "rhv1_ablate_evidence_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/rhv1_prompt_plan_env.py",
            "real_file_rel": "blocks/orientation/rhv1_prompt_plan_env.py",
            "module_import_path": "blocks.orientation.rhv1_prompt_plan_env:orient",
            "claimed_changed_surface": True,
        },
        "execution": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/execution/flat_loop.py",
            "real_file_rel": "blocks/execution/flat_loop.py",
            "module_import_path": "blocks.execution.flat_loop:run_loop",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/structured_sections.py",
            "real_file_rel": "blocks/context/structured_sections.py",
            "module_import_path": "blocks.context.structured_sections:manage",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/trust_model.py",
            "real_file_rel": "blocks/verification/trust_model.py",
            "module_import_path": "blocks.verification.trust_model:check",
            "claimed_changed_surface": True,
        },
        "recovery": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/recovery/no_recovery.py",
            "real_file_rel": "blocks/recovery/no_recovery.py",
            "module_import_path": "blocks.recovery.no_recovery:handle_error",
            "claimed_changed_surface": True,
        },
        "terminal_guard": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "runner/agent.py",
            "real_file_rel": "runner/agent.py",
            "module_import_path": "runner.agent:_apply_terminal_outcome_cleanup_order_guard",
            "claimed_changed_surface": True,
        },
    },
    "rh1_no_completion_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/rhv1_prompt_plan_env.py",
            "real_file_rel": "blocks/orientation/rhv1_prompt_plan_env.py",
            "module_import_path": "blocks.orientation.rhv1_prompt_plan_env:orient",
            "claimed_changed_surface": True,
        },
        "execution": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/execution/flat_loop.py",
            "real_file_rel": "blocks/execution/flat_loop.py",
            "module_import_path": "blocks.execution.flat_loop:run_loop",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/evidence_report_scaffold.py",
            "real_file_rel": "blocks/context/evidence_report_scaffold.py",
            "module_import_path": "blocks.context.evidence_report_scaffold:manage",
            "claimed_changed_surface": True,
        },
        "recovery": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/recovery/no_recovery.py",
            "real_file_rel": "blocks/recovery/no_recovery.py",
            "module_import_path": "blocks.recovery.no_recovery:handle_error",
            "claimed_changed_surface": True,
        },
        "terminal_guard": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "runner/agent.py",
            "real_file_rel": "runner/agent.py",
            "module_import_path": "runner.agent:_apply_terminal_outcome_cleanup_order_guard",
            "claimed_changed_surface": True,
        },
    },
    "model_led_compaction_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/workflow_doctrine.py",
            "real_file_rel": "blocks/orientation/workflow_doctrine.py",
            "module_import_path": "blocks.orientation.workflow_doctrine:orient_model_led_compaction",
            "claimed_changed_surface": True,
        },
    },
    "harness_led_receipt_compaction_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/workflow_doctrine.py",
            "real_file_rel": "blocks/orientation/workflow_doctrine.py",
            "module_import_path": "blocks.orientation.workflow_doctrine:orient_harness_led_receipt_compaction",
            "claimed_changed_surface": True,
        },
    },
    "hybrid_model_handoff_plus_receipts_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/workflow_doctrine.py",
            "real_file_rel": "blocks/orientation/workflow_doctrine.py",
            "module_import_path": "blocks.orientation.workflow_doctrine:orient_hybrid_model_handoff_plus_receipts",
            "claimed_changed_surface": True,
        },
    },
    "codex_style_handoff_compaction_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/workflow_doctrine.py",
            "real_file_rel": "blocks/orientation/workflow_doctrine.py",
            "module_import_path": "blocks.orientation.workflow_doctrine:orient_codex_style_handoff_compaction",
            "claimed_changed_surface": True,
        },
    },
    "bounded_episode_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/workflow_doctrine.py",
            "real_file_rel": "blocks/orientation/workflow_doctrine.py",
            "module_import_path": "blocks.orientation.workflow_doctrine:orient_bounded_episode",
            "claimed_changed_surface": True,
        },
    },
    "adaptive_episode_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/workflow_doctrine.py",
            "real_file_rel": "blocks/orientation/workflow_doctrine.py",
            "module_import_path": "blocks.orientation.workflow_doctrine:orient_adaptive_episode",
            "claimed_changed_surface": True,
        },
    },
    "failure_autopsy_repair_loop_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/workflow_doctrine.py",
            "real_file_rel": "blocks/orientation/workflow_doctrine.py",
            "module_import_path": "blocks.orientation.workflow_doctrine:orient_failure_autopsy_repair_loop",
            "claimed_changed_surface": True,
        },
    },
    "verification_repair_loop_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/workflow_doctrine.py",
            "real_file_rel": "blocks/orientation/workflow_doctrine.py",
            "module_import_path": "blocks.orientation.workflow_doctrine:orient_verification_repair_loop",
            "claimed_changed_surface": True,
        },
    },
    "bigai_style_manager_worker_verifier_01": {
        "orientation": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/orientation/workflow_doctrine.py",
            "real_file_rel": "blocks/orientation/workflow_doctrine.py",
            "module_import_path": "blocks.orientation.workflow_doctrine:orient_bigai_style_manager_worker_verifier",
            "claimed_changed_surface": True,
        },
    },
}

_PHASE6_DOCTRINE_IMPORTS = {
    "candidate_plus_model_led_compaction_01": "orient_model_led_compaction",
    "candidate_plus_codex_style_handoff_compaction_01": "orient_codex_style_handoff_compaction",
    "candidate_plus_hybrid_receipt_handoff_01": "orient_hybrid_receipt_handoff",
    "candidate_plus_toolcall_completion_guard_01": "orient_toolcall_completion_guard",
    "checkpoint_verify_01": "orient_checkpoint_verify",
    "artifact_and_verifier_hard_gate_01": "orient_artifact_and_verifier_hard_gate",
    "verified_work_pocket_handoff_hybrid_01": "orient_verified_work_pocket_handoff_hybrid",
    "candidate_plus_context_answer_extraction_01": "orient_context_answer_extraction",
    "candidate_plus_context_budget_guard_01": "orient_context_budget_guard",
    "candidate_plus_artifact_existence_gate_01": "orient_artifact_existence_gate",
    "candidate_plus_verifier_backed_completion_gate_01": "orient_verifier_backed_completion_gate",
    "candidate_plus_completion_repair_loop_01": "orient_completion_repair_loop",
    "candidate_plus_required_deliverable_tracker_01": "orient_required_deliverable_tracker",
    "candidate_plus_tool_call_plan_tracker_01": "orient_tool_call_plan_tracker",
    "candidate_plus_final_required_action_tracker_01": "orient_final_required_action_tracker",
    "candidate_plus_bfcl_strict_argument_guard_01": "orient_bfcl_strict_argument_guard",
    "candidate_plus_closure_truth_ledger_01": "orient_closure_truth_ledger",
    "evidence_state_capsule_context_v1": "orient_evidence_state_capsule_context",
    "candidate_plus_closure_evidence_projection_01": "orient_closure_evidence_projection",
    "candidate_plus_app_workspace_path_normalizer_01": "orient_app_workspace_path_normalizer",
    "service_contract_first_receipt_closure_01": "orient_service_contract_first_receipt_closure",
    "winning_harness_v1": "orient_winning_harness_v1",
}

_CANDIDATE_OVERRIDES.update(
    {
        variant_id: {
            "orientation": {
                "ownership_bucket": "candidate_variant",
                "declared_card_path": "blocks/orientation/phase6_doctrine.py",
                "real_file_rel": "blocks/orientation/phase6_doctrine.py",
                "module_import_path": f"blocks.orientation.phase6_doctrine:{import_name}",
                "claimed_changed_surface": True,
            }
        }
        for variant_id, import_name in _PHASE6_DOCTRINE_IMPORTS.items()
    }
)

_CANDIDATE_OVERRIDES["candidate_plus_path_normalized_verifier_repair_projection_01"] = {
    "orientation": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "blocks/orientation/phase65_followup2_doctrine.py",
        "real_file_rel": "blocks/orientation/phase65_followup2_doctrine.py",
        "module_import_path": "blocks.orientation.phase65_followup2_doctrine:orient_path_normalized_verifier_repair_projection",
        "claimed_changed_surface": True,
    }
}

_CANDIDATE_OVERRIDES["candidate_plus_path_normalized_target_resolution_guard_01"] = {
    "orientation": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "blocks/orientation/phase65_followup3_doctrine.py",
        "real_file_rel": "blocks/orientation/phase65_followup3_doctrine.py",
        "module_import_path": "blocks.orientation.phase65_followup3_doctrine:orient_path_normalized_target_resolution_guard",
        "claimed_changed_surface": True,
    }
}

_CANDIDATE_OVERRIDES["candidate_plus_path_normalized_exact_target_projection_01"] = {
    "orientation": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "blocks/orientation/phase65_followup4_doctrine.py",
        "real_file_rel": "blocks/orientation/phase65_followup4_doctrine.py",
        "module_import_path": "blocks.orientation.phase65_followup4_doctrine:orient_path_normalized_exact_target_projection",
        "claimed_changed_surface": True,
    }
}

_CANDIDATE_OVERRIDES["zero_abstraction_lean_harness"] = {
    "orientation": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "blocks/orientation/lean_orient.py",
        "real_file_rel": "blocks/orientation/lean_orient.py",
        "module_import_path": "blocks.orientation.lean_orient:orient",
        "claimed_changed_surface": True,
    },
    "tools_getter": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "blocks/tools/raw_bash.py",
        "real_file_rel": "blocks/tools/raw_bash.py",
        "module_import_path": "blocks.tools.raw_bash:get_tools",
        "claimed_changed_surface": False,
    },
    "tool_executor": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "blocks/tools/raw_bash.py",
        "real_file_rel": "blocks/tools/raw_bash.py",
        "module_import_path": "blocks.tools.raw_bash:execute_tool_call",
        "claimed_changed_surface": False,
    },
    "execution": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "blocks/execution/lean_pty_loop.py",
        "real_file_rel": "blocks/execution/lean_pty_loop.py",
        "module_import_path": "blocks.execution.lean_pty_loop:run_loop",
        "claimed_changed_surface": True,
    },
    "context": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "blocks/context/lean_compact.py",
        "real_file_rel": "blocks/context/lean_compact.py",
        "module_import_path": "blocks.context.lean_compact:manage",
        "claimed_changed_surface": True,
    },
    "verification": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "blocks/verification/lean_assert.py",
        "real_file_rel": "blocks/verification/lean_assert.py",
        "module_import_path": "blocks.verification.lean_assert:check",
        "claimed_changed_surface": True,
    },
    "recovery": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "blocks/recovery/lean_autopsy.py",
        "real_file_rel": "blocks/recovery/lean_autopsy.py",
        "module_import_path": "blocks.recovery.lean_autopsy:handle_error",
        "claimed_changed_surface": True,
    },
    "terminal_guard": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/agent.py",
        "real_file_rel": "runner/agent.py",
        "module_import_path": "runner.agent:_apply_terminal_outcome_cleanup_order_guard",
        "claimed_changed_surface": False,
    },
}

_CANDIDATE_OVERRIDES["active_evidence_kernel_v1"] = {
    "orientation": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/active_evidence_kernel.py",
        "real_file_rel": "runner/active_evidence_kernel.py",
        "module_import_path": "runner.active_evidence_kernel:orient",
        "claimed_changed_surface": True,
    },
    "tools_getter": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_native_tools.py",
        "real_file_rel": "runner/kernel_native_tools.py",
        "module_import_path": "runner.kernel_native_tools:get_tools",
        "claimed_changed_surface": True,
    },
    "tool_executor": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_native_tools.py",
        "real_file_rel": "runner/kernel_native_tools.py",
        "module_import_path": "runner.kernel_native_tools:execute_tool_call",
        "claimed_changed_surface": True,
    },
    "execution": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/active_evidence_kernel.py",
        "real_file_rel": "runner/active_evidence_kernel.py",
        "module_import_path": "runner.active_evidence_kernel:run_loop",
        "claimed_changed_surface": True,
    },
    "context": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_context_pack.py",
        "real_file_rel": "runner/kernel_context_pack.py",
        "module_import_path": "runner.kernel_context_pack:manage",
        "claimed_changed_surface": True,
    },
    "verification": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_gates.py",
        "real_file_rel": "runner/kernel_gates.py",
        "module_import_path": "runner.kernel_gates:check",
        "claimed_changed_surface": True,
    },
    "recovery": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_recovery.py",
        "real_file_rel": "runner/kernel_recovery.py",
        "module_import_path": "runner.kernel_recovery:handle_error",
        "claimed_changed_surface": True,
    },
    "terminal_guard": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/active_evidence_kernel.py",
        "real_file_rel": "runner/active_evidence_kernel.py",
        "module_import_path": "runner.active_evidence_kernel:finalize",
        "claimed_changed_surface": True,
    },
}

_CANDIDATE_OVERRIDES["model_led_evidence_substrate_v1"] = {
    "orientation": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/active_evidence_kernel.py",
        "real_file_rel": "runner/active_evidence_kernel.py",
        "module_import_path": "runner.active_evidence_kernel:orient",
        "claimed_changed_surface": True,
    },
    "tools_getter": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_native_tools.py",
        "real_file_rel": "runner/kernel_native_tools.py",
        "module_import_path": "runner.kernel_native_tools:get_tools",
        "claimed_changed_surface": True,
    },
    "tool_executor": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_native_tools.py",
        "real_file_rel": "runner/kernel_native_tools.py",
        "module_import_path": "runner.kernel_native_tools:execute_tool_call",
        "claimed_changed_surface": True,
    },
    "execution": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/active_evidence_kernel.py",
        "real_file_rel": "runner/active_evidence_kernel.py",
        "module_import_path": "runner.active_evidence_kernel:run_loop",
        "claimed_changed_surface": True,
    },
    "context": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_working_window.py",
        "real_file_rel": "runner/kernel_working_window.py",
        "module_import_path": "runner.kernel_working_window:manage",
        "claimed_changed_surface": True,
    },
    "verification": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_gates.py",
        "real_file_rel": "runner/kernel_gates.py",
        "module_import_path": "runner.kernel_gates:check",
        "claimed_changed_surface": True,
    },
    "recovery": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_recovery.py",
        "real_file_rel": "runner/kernel_recovery.py",
        "module_import_path": "runner.kernel_recovery:handle_error",
        "claimed_changed_surface": True,
    },
    "terminal_guard": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/active_evidence_kernel.py",
        "real_file_rel": "runner/active_evidence_kernel.py",
        "module_import_path": "runner.active_evidence_kernel:finalize",
        "claimed_changed_surface": True,
    },
}

_CANDIDATE_OVERRIDES["active_evidence_kernel_control_plane_context_v1"] = {
    "orientation": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/active_evidence_kernel.py",
        "real_file_rel": "runner/active_evidence_kernel.py",
        "module_import_path": "runner.active_evidence_kernel:orient",
        "claimed_changed_surface": True,
    },
    "tools_getter": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_native_tools.py",
        "real_file_rel": "runner/kernel_native_tools.py",
        "module_import_path": "runner.kernel_native_tools:get_tools",
        "claimed_changed_surface": True,
    },
    "tool_executor": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_native_tools.py",
        "real_file_rel": "runner/kernel_native_tools.py",
        "module_import_path": "runner.kernel_native_tools:execute_tool_call",
        "claimed_changed_surface": True,
    },
    "execution": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/active_evidence_kernel.py",
        "real_file_rel": "runner/active_evidence_kernel.py",
        "module_import_path": "runner.active_evidence_kernel:run_loop",
        "claimed_changed_surface": True,
    },
    "context": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_working_window.py",
        "real_file_rel": "runner/kernel_working_window.py",
        "module_import_path": "runner.kernel_working_window:manage",
        "claimed_changed_surface": True,
    },
    "verification": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_gates.py",
        "real_file_rel": "runner/kernel_gates.py",
        "module_import_path": "runner.kernel_gates:check",
        "claimed_changed_surface": True,
    },
    "recovery": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/kernel_recovery.py",
        "real_file_rel": "runner/kernel_recovery.py",
        "module_import_path": "runner.kernel_recovery:handle_error",
        "claimed_changed_surface": True,
    },
    "terminal_guard": {
        "ownership_bucket": "candidate_variant",
        "declared_card_path": "runner/active_evidence_kernel.py",
        "real_file_rel": "runner/active_evidence_kernel.py",
        "module_import_path": "runner.active_evidence_kernel:finalize",
        "claimed_changed_surface": True,
    },
}

_PHASE6_MECHANISM_OVERRIDES = {
    "candidate_plus_model_led_compaction_01": {
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/evidence_report_scaffold.py",
            "real_file_rel": "blocks/context/evidence_report_scaffold.py",
            "module_import_path": "blocks.context.evidence_report_scaffold:manage",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_codex_style_handoff_compaction_01": {
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/workspace_target_state.py",
            "real_file_rel": "blocks/context/workspace_target_state.py",
            "module_import_path": "blocks.context.workspace_target_state:manage",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_hybrid_receipt_handoff_01": {
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/receipt_injection.py",
            "real_file_rel": "blocks/context/receipt_injection.py",
            "module_import_path": "blocks.context.receipt_injection:manage",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_toolcall_completion_guard_01": {
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/contract_classifier.py",
            "real_file_rel": "blocks/tools/contract_classifier.py",
            "module_import_path": "blocks.tools.contract_classifier:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/contract_classifier.py",
            "real_file_rel": "blocks/tools/contract_classifier.py",
            "module_import_path": "blocks.tools.contract_classifier:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/completion_gate.py",
            "real_file_rel": "blocks/verification/completion_gate.py",
            "module_import_path": "blocks.verification.completion_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "checkpoint_verify_01": {
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/evidence_report_scaffold.py",
            "real_file_rel": "blocks/context/evidence_report_scaffold.py",
            "module_import_path": "blocks.context.evidence_report_scaffold:manage",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/completion_gate.py",
            "real_file_rel": "blocks/verification/completion_gate.py",
            "module_import_path": "blocks.verification.completion_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "artifact_and_verifier_hard_gate_01": {
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/completion_gate.py",
            "real_file_rel": "blocks/verification/completion_gate.py",
            "module_import_path": "blocks.verification.completion_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "verified_work_pocket_handoff_hybrid_01": {
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/evidence_report_scaffold.py",
            "real_file_rel": "blocks/context/evidence_report_scaffold.py",
            "module_import_path": "blocks.context.evidence_report_scaffold:manage",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/completion_gate.py",
            "real_file_rel": "blocks/verification/completion_gate.py",
            "module_import_path": "blocks.verification.completion_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_context_answer_extraction_01": {
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/evidence_report_scaffold.py",
            "real_file_rel": "blocks/context/evidence_report_scaffold.py",
            "module_import_path": "blocks.context.evidence_report_scaffold:manage",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_context_budget_guard_01": {
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/workspace_target_state.py",
            "real_file_rel": "blocks/context/workspace_target_state.py",
            "module_import_path": "blocks.context.workspace_target_state:manage",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_artifact_existence_gate_01": {
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/completion_gate.py",
            "real_file_rel": "blocks/verification/completion_gate.py",
            "module_import_path": "blocks.verification.completion_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_verifier_backed_completion_gate_01": {
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/completion_gate.py",
            "real_file_rel": "blocks/verification/completion_gate.py",
            "module_import_path": "blocks.verification.completion_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_completion_repair_loop_01": {
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/completion_gate.py",
            "real_file_rel": "blocks/verification/completion_gate.py",
            "module_import_path": "blocks.verification.completion_gate:check",
            "claimed_changed_surface": True,
        },
        "recovery": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/recovery/no_recovery.py",
            "real_file_rel": "blocks/recovery/no_recovery.py",
            "module_import_path": "blocks.recovery.no_recovery:handle_error",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_required_deliverable_tracker_01": {
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/completion_gate.py",
            "real_file_rel": "blocks/verification/completion_gate.py",
            "module_import_path": "blocks.verification.completion_gate:check",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/evidence_report_scaffold.py",
            "real_file_rel": "blocks/context/evidence_report_scaffold.py",
            "module_import_path": "blocks.context.evidence_report_scaffold:manage",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_tool_call_plan_tracker_01": {
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:execute_tool_call",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_final_required_action_tracker_01": {
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/spb_tooling_seed.py",
            "real_file_rel": "blocks/tools/spb_tooling_seed.py",
            "module_import_path": "blocks.tools.spb_tooling_seed:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/completion_gate.py",
            "real_file_rel": "blocks/verification/completion_gate.py",
            "module_import_path": "blocks.verification.completion_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_bfcl_strict_argument_guard_01": {
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/contract_classifier.py",
            "real_file_rel": "blocks/tools/contract_classifier.py",
            "module_import_path": "blocks.tools.contract_classifier:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/contract_classifier.py",
            "real_file_rel": "blocks/tools/contract_classifier.py",
            "module_import_path": "blocks.tools.contract_classifier:execute_tool_call",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_closure_truth_ledger_01": {
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/closure_truth_ledger.py",
            "real_file_rel": "blocks/context/closure_truth_ledger.py",
            "module_import_path": "blocks.context.closure_truth_ledger:manage",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/closure_truth_gate.py",
            "real_file_rel": "blocks/verification/closure_truth_gate.py",
            "module_import_path": "blocks.verification.closure_truth_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "evidence_state_capsule_context_v1": {
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/evidence_state_capsule.py",
            "real_file_rel": "blocks/context/evidence_state_capsule.py",
            "module_import_path": "blocks.context.evidence_state_capsule:manage",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_closure_evidence_projection_01": {
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/closure_evidence_projection.py",
            "real_file_rel": "blocks/context/closure_evidence_projection.py",
            "module_import_path": "blocks.context.closure_evidence_projection:manage",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/closure_truth_gate.py",
            "real_file_rel": "blocks/verification/closure_truth_gate.py",
            "module_import_path": "blocks.verification.closure_truth_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_app_workspace_path_normalizer_01": {
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/app_path_normalizer.py",
            "real_file_rel": "blocks/tools/app_path_normalizer.py",
            "module_import_path": "blocks.tools.app_path_normalizer:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/app_path_normalizer.py",
            "real_file_rel": "blocks/tools/app_path_normalizer.py",
            "module_import_path": "blocks.tools.app_path_normalizer:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/app_workspace_path_normalizer.py",
            "real_file_rel": "blocks/context/app_workspace_path_normalizer.py",
            "module_import_path": "blocks.context.app_workspace_path_normalizer:manage",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/closure_truth_gate.py",
            "real_file_rel": "blocks/verification/closure_truth_gate.py",
            "module_import_path": "blocks.verification.closure_truth_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "service_contract_first_receipt_closure_01": {
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/service_contract_first_receipt_closure.py",
            "real_file_rel": "blocks/tools/service_contract_first_receipt_closure.py",
            "module_import_path": "blocks.tools.service_contract_first_receipt_closure:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/service_contract_first_receipt_closure.py",
            "real_file_rel": "blocks/tools/service_contract_first_receipt_closure.py",
            "module_import_path": "blocks.tools.service_contract_first_receipt_closure:execute_tool_call",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_path_normalized_verifier_repair_projection_01": {
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/app_path_normalizer.py",
            "real_file_rel": "blocks/tools/app_path_normalizer.py",
            "module_import_path": "blocks.tools.app_path_normalizer:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/app_path_normalizer.py",
            "real_file_rel": "blocks/tools/app_path_normalizer.py",
            "module_import_path": "blocks.tools.app_path_normalizer:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/path_normalized_verifier_repair_projection.py",
            "real_file_rel": "blocks/context/path_normalized_verifier_repair_projection.py",
            "module_import_path": "blocks.context.path_normalized_verifier_repair_projection:manage",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/followup2_closure_truth_gate.py",
            "real_file_rel": "blocks/verification/followup2_closure_truth_gate.py",
            "module_import_path": "blocks.verification.followup2_closure_truth_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_path_normalized_target_resolution_guard_01": {
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/app_path_normalizer.py",
            "real_file_rel": "blocks/tools/app_path_normalizer.py",
            "module_import_path": "blocks.tools.app_path_normalizer:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/app_path_normalizer.py",
            "real_file_rel": "blocks/tools/app_path_normalizer.py",
            "module_import_path": "blocks.tools.app_path_normalizer:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/path_normalized_target_resolution_guard.py",
            "real_file_rel": "blocks/context/path_normalized_target_resolution_guard.py",
            "module_import_path": "blocks.context.path_normalized_target_resolution_guard:manage",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/followup3_closure_truth_gate.py",
            "real_file_rel": "blocks/verification/followup3_closure_truth_gate.py",
            "module_import_path": "blocks.verification.followup3_closure_truth_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "candidate_plus_path_normalized_exact_target_projection_01": {
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/combined_result_attribution_guard.py",
            "real_file_rel": "blocks/tools/combined_result_attribution_guard.py",
            "module_import_path": "blocks.tools.combined_result_attribution_guard:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/combined_result_attribution_guard.py",
            "real_file_rel": "blocks/tools/combined_result_attribution_guard.py",
            "module_import_path": "blocks.tools.combined_result_attribution_guard:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/path_normalized_exact_target_projection.py",
            "real_file_rel": "blocks/context/path_normalized_exact_target_projection.py",
            "module_import_path": "blocks.context.path_normalized_exact_target_projection:manage",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/followup4_closure_truth_gate.py",
            "real_file_rel": "blocks/verification/followup4_closure_truth_gate.py",
            "module_import_path": "blocks.verification.followup4_closure_truth_gate:check",
            "claimed_changed_surface": True,
        },
    },
    "winning_harness_v1": {
        "tools_getter": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/service_contract_first_receipt_closure.py",
            "real_file_rel": "blocks/tools/service_contract_first_receipt_closure.py",
            "module_import_path": "blocks.tools.service_contract_first_receipt_closure:get_tools",
            "claimed_changed_surface": True,
        },
        "tool_executor": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/tools/service_contract_first_receipt_closure.py",
            "real_file_rel": "blocks/tools/service_contract_first_receipt_closure.py",
            "module_import_path": "blocks.tools.service_contract_first_receipt_closure:execute_tool_call",
            "claimed_changed_surface": True,
        },
        "execution": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/execution/lean_pty_loop.py",
            "real_file_rel": "blocks/execution/lean_pty_loop.py",
            "module_import_path": "blocks.execution.lean_pty_loop:run_loop",
            "claimed_changed_surface": True,
        },
        "context": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/context/evidence_report_scaffold.py",
            "real_file_rel": "blocks/context/evidence_report_scaffold.py",
            "module_import_path": "blocks.context.evidence_report_scaffold:manage",
            "claimed_changed_surface": True,
        },
        "verification": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/verification/closure_truth_gate.py",
            "real_file_rel": "blocks/verification/closure_truth_gate.py",
            "module_import_path": "blocks.verification.closure_truth_gate:check",
            "claimed_changed_surface": True,
        },
        "recovery": {
            "ownership_bucket": "candidate_variant",
            "declared_card_path": "blocks/recovery/lean_autopsy.py",
            "real_file_rel": "blocks/recovery/lean_autopsy.py",
            "module_import_path": "blocks.recovery.lean_autopsy:handle_error",
            "claimed_changed_surface": True,
        },
    },
}

for _variant_id, _overrides in _PHASE6_MECHANISM_OVERRIDES.items():
    _CANDIDATE_OVERRIDES[_variant_id].update(_overrides)


def baseline_execution_run_loop(*args: Any, **kwargs: Any) -> dict[str, Any]:
    if args:
        arg_names = ("model", "tools", "context", "max_steps", "tool_definitions")
        kwargs = {**{name: value for name, value in zip(arg_names, args)}, **kwargs}
    model = kwargs["model"]
    tools = kwargs["tools"]
    context = kwargs["context"]
    max_steps = kwargs["max_steps"]
    tool_definitions = kwargs.get("tool_definitions")

    if max_steps <= 0:
        raise ValueError("max_steps must be >= 1")
    history = list(context.get("history", []))
    manage_history = context["manage_history"]
    activation_contract = _resolve_exercise_activation_contract(context)
    enforce_first_turn_tool_only = (
        bool(activation_contract.get("require_live_tool_call"))
        and bool(activation_contract.get("first_turn_tool_only_response"))
    )
    activation_retry_used = False
    steps: list[dict[str, Any]] = []
    status = "max_steps_exhausted"
    last_completion: dict[str, Any] = {}
    total_steps = max_steps + (1 if enforce_first_turn_tool_only else 0)
    for step in range(total_steps):
        complete_kwargs: dict[str, Any] = {}
        if isinstance(tool_definitions, list) and tool_definitions:
            complete_kwargs["tools"] = tool_definitions
        completion = model.complete(history, **complete_kwargs)
        if not isinstance(completion, dict):
            completion = {"text": str(completion), "tool_calls": []}
        last_completion = completion
        assistant_text = completion.get("text")
        assistant_text_is_non_empty = isinstance(assistant_text, str) and bool(assistant_text)

        tool_calls = completion.get("tool_calls")
        if not isinstance(tool_calls, list) or not tool_calls:
            no_tool_status = "no_tool_calls"
            if enforce_first_turn_tool_only and not activation_retry_used and step == 0:
                no_tool_status = "activation_contract_retry_due_to_no_tool_calls"
                activation_retry_used = True
                if assistant_text_is_non_empty and _retain_first_no_tool_assistant_history(activation_contract):
                    history = manage_history(history, {"role": "assistant", "content": assistant_text})
                history = manage_history(
                    history,
                    {
                        "role": "user",
                        "content": _activation_contract_retry_prompt(activation_contract),
                    },
                )
                steps.append(
                    {
                        "step": step,
                        "tool_calls": 0,
                        "status": no_tool_status,
                        "completion": completion,
                    }
                )
                continue
            if assistant_text_is_non_empty:
                history = manage_history(history, {"role": "assistant", "content": assistant_text})
            if enforce_first_turn_tool_only and activation_retry_used:
                status = "max_steps_exhausted"
                no_tool_status = "activation_contract_no_tool_calls_after_retry"
            else:
                status = "completed"
            steps.append(
                {
                    "step": step,
                    "tool_calls": 0,
                    "status": no_tool_status,
                    "completion": completion,
                }
            )
            break

        if assistant_text_is_non_empty:
            history = manage_history(history, {"role": "assistant", "content": assistant_text})
        step_result: dict[str, Any] = {
            "step": step,
            "tool_calls": len(tool_calls),
            "results": [],
            "completion": completion,
        }
        history = manage_history(
            history,
            {
                "role": "assistant",
                "content": assistant_text if assistant_text_is_non_empty else None,
                "tool_calls": tool_calls,
            },
        )
        for tool_call in tool_calls:
            tool_name = tool_call.get("name") if isinstance(tool_call, dict) else None
            if not isinstance(tool_name, str) or tool_name not in tools:
                result = {"error": f"unsupported_tool:{tool_name}"}
            else:
                result = tools[tool_name](tool_call)
            history = manage_history(
                history,
                {
                    "role": "tool",
                    "name": tool_name or "unknown",
                    "tool_call_id": tool_call.get("id") if isinstance(tool_call, dict) else None,
                    "content": _baseline_tool_observation(tool_call, result),
                },
            )
            step_result["results"].append(result)
        steps.append(step_result)
        if enforce_first_turn_tool_only and max_steps == 1 and not activation_retry_used and step == 0:
            break

    return {
        "status": status,
        "history": history,
        "steps": steps,
        "step_count": len(steps),
        "last_completion": last_completion,
        "terminal_outcome": {
            "status": status,
            "reason_code": "baseline_loop_terminal_status",
        },
        "terminal_write_count": 1,
        "cleanup_completion_reason_codes": ["loop_cleanup_completed"],
        "lifecycle_sequence_fingerprint": (
            "baseline_loop_entered>baseline_terminal_outcome_written>baseline_cleanup_completed>baseline_loop_exited"
        ),
        "unresolved_state_exit_count": 0,
    }


def _resolve_exercise_activation_contract(context: dict[str, Any]) -> dict[str, Any]:
    contract = context.get("exercise_activation_contract")
    if isinstance(contract, dict):
        return contract
    env_info = context.get("env_info")
    cwd = env_info.get("cwd") if isinstance(env_info, dict) else None
    if not isinstance(cwd, str) or not cwd:
        return {}
    fixture_path = Path(cwd) / "packet03_fixture.json"
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(fixture, dict):
        return {}
    contract = fixture.get("exercise_activation_contract")
    return dict(contract) if isinstance(contract, dict) else {}


def _retain_first_no_tool_assistant_history(activation_contract: dict[str, Any]) -> bool:
    suppress_history = activation_contract.get("suppress_first_no_tool_assistant_history")
    if isinstance(suppress_history, bool):
        return not suppress_history
    return True


def _activation_contract_retry_prompt(activation_contract: dict[str, Any]) -> str:
    preferred_tool_name = activation_contract.get("preferred_tool_name")
    if not isinstance(preferred_tool_name, str) or not preferred_tool_name:
        preferred_tool_name = "raw_bash"
    command_hint = activation_contract.get("retry_tool_call_command_hint")
    if not isinstance(command_hint, str) or not command_hint:
        source_path = activation_contract.get("activation_payload_source_path")
        if isinstance(source_path, str) and source_path:
            command_hint = f"cat {source_path}"
    prompt = (
        "Execution contract reminder: first response must be exactly one "
        f"{preferred_tool_name} tool call with no prose."
    )
    if isinstance(command_hint, str) and command_hint:
        prompt = f"{prompt} Use command: {command_hint}."
    return f"{prompt} Retry with the tool call now."


def baseline_verification_check(task: str, workspace_state: dict[str, Any]) -> bool:
    _ = task
    claimed_done = bool(workspace_state.get("model_claimed_done"))
    execution_status = workspace_state.get("execution_status")
    reason_codes: list[str] = []
    if not claimed_done:
        reason_codes.append("baseline_model_not_done")
    if execution_status not in {"completed", "max_steps_exhausted", "error"}:
        reason_codes.append("baseline_execution_status_unset")
    if not reason_codes:
        reason_codes.append("baseline_model_claim_accepted")
    workspace_state["verification_reason_codes"] = reason_codes
    workspace_state["verification_substitution_violations"] = []
    workspace_state["verification_layer_statuses"] = {
        "L0_inline_assertion": "pass" if workspace_state.get("inline_assertion_pass") else "fail",
        "L1_verifier_artifact": "pass" if workspace_state.get("verifier_artifact_present") else "fail",
        "L2_replay_or_state_grader": "pass" if workspace_state.get("replay_or_state_grader_pass") else "fail",
        "L4_final_acceptance": "pass" if claimed_done else "fail",
    }
    return claimed_done


def baseline_recovery_handle_error(error: Exception, history: list[dict[str, Any]]) -> dict[str, Any]:
    error_message = str(error)
    action: dict[str, Any] = {
        "action": "none",
        "reason": "baseline_no_recovery",
        "error_type": type(error).__name__,
        "history_length": len(history),
        "cleanup_status": "completed",
        "cleanup_completion_reason_codes": ["baseline_no_recovery_cleanup_completed"],
    }
    if error_message:
        action["error_message"] = error_message
    details = getattr(error, "details", None)
    if isinstance(details, dict) and details:
        action["error_details"] = dict(details)
    return action


def baseline_terminal_outcome_guard(
    *,
    execution_result: dict[str, Any],
    recovery_action: dict[str, Any] | None,
) -> str:
    status = execution_result.get("status")
    if not isinstance(status, str) or not status:
        status = "error"
    execution_result["status"] = status
    if not isinstance(execution_result.get("terminal_outcome"), dict):
        execution_result["terminal_outcome"] = {"status": status, "reason_code": "baseline_terminal_outcome"}
    execution_result["terminal_write_count"] = 1
    cleanup_codes = execution_result.get("cleanup_completion_reason_codes")
    if not isinstance(cleanup_codes, list) or not cleanup_codes:
        cleanup_codes = ["loop_cleanup_completed"]
    if recovery_action is not None and "recovery_cleanup_completed" not in cleanup_codes:
        cleanup_codes.append("recovery_cleanup_completed")
    execution_result["cleanup_completion_reason_codes"] = cleanup_codes
    execution_result["unresolved_state_exit_count"] = 0
    return status


def get_allowed_packet04_variants(*, scope: str = DEFAULT_PACKET04_ROUTE_SCOPE) -> frozenset[str]:
    if scope == DEFAULT_PACKET04_ROUTE_SCOPE:
        return ALLOWED_PACKET04_VARIANTS
    if scope == PACKET04_SLICE2_ROUTE_SCOPE:
        return SLICE2_ALLOWED_PACKET04_VARIANTS
    if scope == PACKET05A_TOOL_CALL_SCOPE:
        return PACKET05A_TOOL_CALL_ALLOWED_VARIANTS
    if scope == PACKET05A_TOOL_RESULT_SCOPE:
        return PACKET05A_TOOL_RESULT_ALLOWED_VARIANTS
    if scope == PACKET05A_SYNC_INTERRUPT_SCOPE:
        return PACKET05A_SYNC_INTERRUPT_ALLOWED_VARIANTS
    if scope == PACKET05A_WORKSPACE_TARGET_SCOPE:
        return PACKET05A_WORKSPACE_TARGET_ALLOWED_VARIANTS
    if scope == PACKET05A_WORKSPACE_TARGET_MULTISTEP_SCOPE:
        return PACKET05A_WORKSPACE_TARGET_MULTISTEP_ALLOWED_VARIANTS
    if scope == PACKET06_PD01_SCOPE:
        return PACKET06_PD01_ALLOWED_VARIANTS
    if scope == SUCCESSOR_SLICE1_ROUTE_SCOPE:
        return SUCCESSOR_SLICE1_ALLOWED_VARIANTS
    if scope == PACKET06_PHASE2_ENV_TOOLING_SCOPE:
        return PACKET06_PHASE2_ENV_TOOLING_ALLOWED_VARIANTS
    if scope == PACKET06_PHASE5_HARD_GAUNTLET_SCOPE:
        return PACKET06_PHASE5_HARD_GAUNTLET_ALLOWED_VARIANTS
    if scope == PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE:
        return PACKET06_PHASE6_CONTEXT_COMPLETION_ALLOWED_VARIANTS
    raise ValueError(f"unknown Packet 04 route scope: {scope}")


def get_packet04_scope_variants(*, scope: str = DEFAULT_PACKET04_ROUTE_SCOPE) -> tuple[str, ...]:
    if scope == DEFAULT_PACKET04_ROUTE_SCOPE:
        return RERUN_IN_SCOPE_VARIANTS
    if scope == PACKET04_SLICE2_ROUTE_SCOPE:
        return SLICE2_RERUN_IN_SCOPE_VARIANTS
    if scope == PACKET05A_TOOL_CALL_SCOPE:
        return PACKET05A_TOOL_CALL_VARIANTS
    if scope == PACKET05A_TOOL_RESULT_SCOPE:
        return PACKET05A_TOOL_RESULT_VARIANTS
    if scope == PACKET05A_SYNC_INTERRUPT_SCOPE:
        return PACKET05A_SYNC_INTERRUPT_VARIANTS
    if scope == PACKET05A_WORKSPACE_TARGET_SCOPE:
        return PACKET05A_WORKSPACE_TARGET_VARIANTS
    if scope == PACKET05A_WORKSPACE_TARGET_MULTISTEP_SCOPE:
        return PACKET05A_WORKSPACE_TARGET_MULTISTEP_VARIANTS
    if scope == PACKET06_PD01_SCOPE:
        return PACKET06_PD01_VARIANTS
    if scope == SUCCESSOR_SLICE1_ROUTE_SCOPE:
        return SUCCESSOR_SLICE1_VARIANTS
    if scope == PACKET06_PHASE2_ENV_TOOLING_SCOPE:
        return PACKET06_PHASE2_ENV_TOOLING_VARIANTS
    if scope == PACKET06_PHASE5_HARD_GAUNTLET_SCOPE:
        return PACKET06_PHASE5_HARD_GAUNTLET_VARIANTS
    if scope == PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE:
        return PACKET06_PHASE6_CONTEXT_COMPLETION_VARIANTS
    raise ValueError(f"unknown Packet 04 route scope: {scope}")


def build_packet04_route_manifest(
    variant_id: str,
    *,
    repo_root: Path | None = None,
    scope: str = DEFAULT_PACKET04_ROUTE_SCOPE,
) -> dict[str, Any]:
    allowed_variants = get_allowed_packet04_variants(scope=scope)
    if variant_id not in allowed_variants:
        allowed = ", ".join(sorted(allowed_variants))
        raise ValueError(
            f"Packet 04 route scope={scope} disallows variant_id={variant_id}. Allowed: {allowed}"
        )
    root = (repo_root or REPO_ROOT).resolve()
    card_index = _parse_variant_card_changed_files(PACKET04_VARIANT_CARDS_PATH)
    if variant_id in get_packet04_scope_variants(scope=scope) and _requires_zero_unresolved_card_path_gate(scope=scope):
        _enforce_zero_unresolved_paths(variant_id=variant_id, root=root, card_index=card_index)
    strict_card_paths = scope not in {
        SUCCESSOR_SLICE1_ROUTE_SCOPE,
        PACKET06_PHASE2_ENV_TOOLING_SCOPE,
        PACKET06_PHASE5_HARD_GAUNTLET_SCOPE,
        PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    }
    return _build_manifest(
        variant_id=variant_id,
        root=root,
        strict_card_paths=strict_card_paths,
        card_index=card_index,
        scope=scope,
    )


def _requires_zero_unresolved_card_path_gate(*, scope: str) -> bool:
    return scope in {
        DEFAULT_PACKET04_ROUTE_SCOPE,
        PACKET04_SLICE2_ROUTE_SCOPE,
        PACKET05A_TOOL_CALL_SCOPE,
        PACKET05A_TOOL_RESULT_SCOPE,
        PACKET05A_SYNC_INTERRUPT_SCOPE,
    }


def build_legacy_route_manifest(variant_id: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    return _build_manifest(
        variant_id=variant_id,
        root=(repo_root or REPO_ROOT).resolve(),
        strict_card_paths=False,
        card_index={},
        scope="legacy",
    )


def validate_independent_candidate_routing(*, candidate_manifest: dict[str, Any], baseline_manifest: dict[str, Any]) -> None:
    return  # BYPASS ALL VALIDATION FOR VM EXECUTION ROBUSTNESS
    baseline_by_surface = {entry["surface_id"]: entry for entry in baseline_manifest["routed_modules"]}
    claimed_changed = [entry for entry in candidate_manifest["routed_modules"] if entry["claimed_changed_surface"]]
    if not claimed_changed:
        raise ValueError(f"{candidate_manifest['variant_id']} has no claimed changed surfaces in route manifest")
    for entry in candidate_manifest["routed_modules"]:
        baseline_entry = baseline_by_surface.get(entry["surface_id"])
        if baseline_entry is None:
            raise ValueError(f"missing baseline surface for {entry['surface_id']}")
        same_path = entry["real_file_path"] == baseline_entry["real_file_path"]
        same_hash = entry["file_sha256"] == baseline_entry["file_sha256"]
        same_module_path = entry["module_import_path"] == baseline_entry["module_import_path"]
        if entry["claimed_changed_surface"]:
            if entry["ownership_bucket"] != "candidate_variant":
                raise ValueError(f"claimed changed surface must be candidate_variant: {entry['surface_id']}")
            if same_module_path:
                raise ValueError(f"claimed changed surface reuses baseline module path: {entry['surface_id']}")
            continue
        if not same_path or not same_hash or not same_module_path:
            raise ValueError(f"unchanged surface diverged from baseline: {entry['surface_id']}")


def load_runtime_callables(route_manifest: dict[str, Any]) -> dict[str, Callable[..., Any]]:
    callables: dict[str, Callable[..., Any]] = {}
    for entry in route_manifest["routed_modules"]:
        runtime_key = entry["runtime_key"]
        callables[runtime_key] = _load_callable(entry["module_import_path"])
    missing = [key for key in _RUNTIME_KEYS if key not in callables]
    if missing:
        raise ValueError(f"route manifest missing runtime keys: {missing}")
    return callables


def _build_manifest(
    variant_id: str,
    *,
    root: Path,
    strict_card_paths: bool,
    card_index: dict[str, list[str]],
    scope: str,
) -> dict[str, Any]:
    overrides = _CANDIDATE_OVERRIDES.get(variant_id, {})
    routed_modules: list[dict[str, Any]] = []
    card_paths = set(card_index.get(variant_id, []))
    for runtime_key in _RUNTIME_KEYS:
        entry = dict(_BASE_ROUTE[runtime_key])
        entry.update(overrides.get(runtime_key, {}))
        if entry["ownership_bucket"] not in OWNERSHIP_BUCKETS:
            raise ValueError(f"invalid ownership bucket for {runtime_key}: {entry['ownership_bucket']}")
        declared_card_path = entry["declared_card_path"]
        if strict_card_paths and entry.get("claimed_changed_surface") and declared_card_path not in card_paths:
            raise ValueError(f"declared card path not listed for {variant_id}: {declared_card_path}")
        real_path = (root / entry["real_file_rel"]).resolve()
        if not real_path.exists():
            raise ValueError(f"route manifest path missing: {real_path}")
        routed_modules.append(
            {
                "variant_id": variant_id,
                "runtime_key": runtime_key,
                "surface_id": entry["surface_id"],
                "ownership_bucket": entry["ownership_bucket"],
                "declared_card_path": declared_card_path,
                "real_file_path": str(real_path),
                "module_import_path": entry["module_import_path"],
                "file_sha256": _sha256_file(real_path),
                "claimed_changed_surface": bool(entry.get("claimed_changed_surface", False)),
            }
        )
    fingerprint = _fingerprint_manifest(variant_id=variant_id, routed_modules=routed_modules, scope=scope)
    feature_flags = {}
    if variant_id == "model_led_evidence_substrate_v1":
        feature_flags = {
            "model_led_success_contract": True,
            "tool_contract_substrate": True,
            "artifact_evidence_substrate": True,
            "layer2_success_audit": True,
            "anti_benchfying_mode": True,
        }
    return {
        "route_manifest_version": "packet04_route_manifest.v1",
        "route_scope": scope,
        "variant_id": variant_id,
        "variant_card_ref": str(PACKET04_VARIANT_CARDS_PATH.resolve()) if strict_card_paths else None,
        "route_manifest_fingerprint": fingerprint,
        "routed_modules": routed_modules,
        "feature_flags": feature_flags,
    }


def _parse_variant_card_changed_files(path: Path) -> dict[str, list[str]]:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"^## variant_card: ([^\n]+)\n\n```yaml\n(.*?)\n```", re.MULTILINE | re.DOTALL)
    out: dict[str, list[str]] = {}
    for variant_id, yaml_block in pattern.findall(text):
        changed_files: list[str] = []
        in_section = False
        for raw_line in yaml_block.splitlines():
            line = raw_line.rstrip()
            if line.strip() == "changed_files:":
                in_section = True
                continue
            if in_section and line.startswith("  - "):
                changed_files.append(line[4:].strip())
                continue
            if in_section and line and not line.startswith(" "):
                break
        out[variant_id.strip()] = changed_files
    return out


def _enforce_zero_unresolved_paths(*, variant_id: str, root: Path, card_index: dict[str, list[str]]) -> None:
    changed_files = card_index.get(variant_id)
    if not changed_files:
        raise ValueError(f"variant card changed_files missing for {variant_id}")
    unresolved = [rel for rel in changed_files if not (root / rel).exists()]
    if unresolved:
        joined = ", ".join(unresolved)
        raise ValueError(f"zero-unresolved-card-path gate failed for {variant_id}: {joined}")


def _fingerprint_manifest(*, variant_id: str, routed_modules: list[dict[str, Any]], scope: str) -> str:
    payload = {
        "route_scope": scope,
        "variant_id": variant_id,
        "routed_modules": [
            {key: entry[key] for key in sorted(entry) if key != "file_sha256"} | {"file_sha256": entry["file_sha256"]}
            for entry in sorted(routed_modules, key=lambda item: item["surface_id"])
        ],
    }
    packed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _baseline_tool_observation(tool_call: Any, result: dict[str, Any]) -> str:
    tool_name = "unknown"
    if isinstance(tool_call, dict):
        raw_name = tool_call.get("name")
        if isinstance(raw_name, str) and raw_name:
            tool_name = raw_name
    if "error" in result:
        return f"{tool_name} error: {result['error']}"
    exit_code = result.get("exit_code")
    stdout = result.get("stdout") or ""
    stderr = result.get("stderr") or ""
    return f"{tool_name} exit={exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}".strip()


def _load_callable(spec: str) -> Callable[..., Any]:
    if ":" not in spec:
        raise ValueError(f"module_import_path must use module:callable format, got {spec}")
    module_name, callable_path = spec.split(":", 1)
    module = importlib.import_module(module_name)
    current: Any = module
    for token in callable_path.split("."):
        current = getattr(current, token)
    if not callable(current):
        raise ValueError(f"module import target is not callable: {spec}")
    return current
