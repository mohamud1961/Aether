# Packet 04 Variant Cards (First Buildable Atomic Slice)

Status: draft recommendations only (`human_gate_required: true`)
Scope lock: `changed_files` entries are harness/runtime/block implementation scope only; `evals/atomic/*` remains fixed measurement surface in Packet 04.

## variant_card: v04_vc_01_layered_non_substitution_reason_codes

```yaml
variant_id: v04_vc_01_layered_non_substitution_reason_codes
block_family: VerificationBlock
block_interface: VerificationBlock.check(task, workspace_state) -> verified: bool
source_from_deep_synthesis:
  anchors:
    - claim_ref: mm.w03.artifact_backed_postcondition_proof
      source: tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md
    - claim_ref: mm.w03.layered_verifier_grader_replay_separation
      source: tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md
    - claim_ref: ft.w02.verifier_completion_vs_final_acceptance_divergence
      source: tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md
    - claim_ref: vfs.w02.vf_pc_02_layered_acceptance_survives
      source: tracking/collab/stage_02_synthesis/variant_family_seeds/synthesis/principal_synthesis.md
observed_trace_or_eval_evidence:
  - packet_03 eval card for ae_completion_layer_contract_guard reports layered non-substitution as required and promotion-relevant
  - packet_03 closeout marks this surface accepted and usable now
mechanism_claim: Harden layered completion acceptance so final acceptance cannot substitute for missing verifier/replay evidence; require stable missing-layer reason codes.
target_failure: completion_false_positive
anti_benchmarkifying_risk: variant may overfit to known missing-layer templates while still failing unseen layer omission patterns.
expected_improvement: lower false-clean-pass rate and lower verifier/final divergence on deterministic completion contract fixtures.
expected_failure_mode: overly strict layer checks may reject valid runs when optional metadata is absent but core evidence is present.
complexity_cost: low_to_medium (new deterministic reason-code checks and envelope wiring in verification path).
token_cost_expectation: negligible on deterministic required eval; no model dependency for required gate.
changed_files:
  - blocks/verification/layered_acceptance_guard.py
  - blocks/verification/trust_model.py
  - runner/evaluator.py
required_atomic_eval: ae_completion_layer_contract_guard
required_atomic_eval_status: accepted_packet_03_surface
anticipated_interaction_eval: completion_x_tool_result_attribution_interaction_probe
anticipated_interaction_eval_status: blocked_until_packet_05
anticipated_transfer_eval: terminalbench_development_transfer_completion_integrity_set_v1
anticipated_transfer_eval_status: anticipated
promotion_threshold: beats reference baseline on required atomic eval and passes at least one sibling corroborating completion diagnostic with no substitution violations.
retirement_condition: retire if gains disappear under adversarial perturbations or if transfer shows increased false-negative completion without reducing false positives.
bounded_claims:
  - atomic-first bounded claim only
  - no system-level promotion claim in packet_04
telemetry_required:
  - verifier_final_contradiction_summary
  - missing_layer_reason_code_counts
  - score_envelope_layer_presence_vector
  - run_header_settings_fingerprint
model_policy:
  screening_default: oauth:gpt-5.4-mini
  promotion_tier: gpt-5.3-codex
  deterministic_eval_override: no_model
  note: gpt-5.3-codex is reserved for survivor confirmation and tie-break claims only.
```

## variant_card: v04_ex_01_single_terminal_outcome_cleanup_order_guard

```yaml
variant_id: v04_ex_01_single_terminal_outcome_cleanup_order_guard
block_family: ExecutionBlock
block_interface: ExecutionBlock.run_loop(model, tools, context, max_steps) -> result
source_from_deep_synthesis:
  anchors:
    - claim_ref: mm.w05.process_lifecycle_cancellation_boundary_control
      source: tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md
    - claim_ref: ft.w04.process_lifecycle_cancellation_boundary_failure
      source: tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md
    - claim_ref: ft.w02.recovery_resume_state_index_fragility
      source: tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md
    - claim_ref: vfs.w02.vf_pc_03_lifecycle_cleanup_hardening_survives
      source: tracking/collab/stage_02_synthesis/variant_family_seeds/synthesis/principal_synthesis.md
observed_trace_or_eval_evidence:
  - packet_03 eval card for ae_lifecycle_terminality_contract_guard marks single-terminal-write and cleanup sequencing as required contract
  - packet_03 closeout marks lifecycle terminality guard accepted and usable now
mechanism_claim: enforce one terminal outcome and deterministic cleanup ordering so cancellation/stop boundaries cannot yield fake completion.
target_failure: process_lifecycle_and_cancellation_boundary_failure
anti_benchmarkifying_risk: variant may optimize for explicit cancellation fixtures but miss long-horizon lifecycle degradation.
expected_improvement: fewer duplicate terminal writes and fewer cleanup-order violations under deterministic lifecycle fixtures.
expected_failure_mode: aggressive terminal lock may truncate valid late tool outputs needed for honest failure attribution.
complexity_cost: medium (lifecycle state machine tightening and cleanup finalization checks).
token_cost_expectation: negligible on required deterministic eval; potential small runtime overhead from extra lifecycle assertions.
changed_files:
  - blocks/execution/flat_loop.py
  - blocks/recovery/no_recovery.py
  - runner/agent.py
required_atomic_eval: ae_lifecycle_terminality_contract_guard
required_atomic_eval_status: accepted_packet_03_surface
anticipated_interaction_eval: lifecycle_x_tool_return_race_probe
anticipated_interaction_eval_status: blocked_until_packet_05
anticipated_transfer_eval: terminalbench_development_transfer_lifecycle_stability_set_v1
anticipated_transfer_eval_status: anticipated
promotion_threshold: deterministic lifecycle pass with identical terminal-write cardinality across reruns plus no cleanup-order regressions on sibling diagnostics.
retirement_condition: retire if variant increases unresolved termination states or causes regression in workspace integrity under transfer runs.
bounded_claims:
  - atomic contract claim only
  - interruption robustness remains bounded until non-bounded sync-interrupt surface exists
telemetry_required:
  - lifecycle_sequence_fingerprint
  - terminal_write_count
  - cleanup_completion_reason_codes
  - unresolved_state_exit_count
model_policy:
  screening_default: oauth:gpt-5.4-mini
  promotion_tier: gpt-5.3-codex
  deterministic_eval_override: no_model
  note: stronger model tier used only for survivor confirmation/tie-breaks.
```

## variant_card: v04_ex_02_cwd_workdir_invariant_propagation_guard

```yaml
variant_id: v04_ex_02_cwd_workdir_invariant_propagation_guard
block_family: ExecutionBlock
block_interface: ExecutionBlock.run_loop(model, tools, context, max_steps) -> result
source_from_deep_synthesis:
  anchors:
    - claim_ref: mm.w05.cwd_workdir_path_contract
      source: tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md
    - claim_ref: mm.w04.explicit_artifact_continuity_workspace_state
      source: tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md
    - claim_ref: ft.w03.workspace_repo_branch_path_drift
      source: tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md
    - claim_ref: ft.w04.cwd_workdir_path_contract_failure
      source: tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md
    - claim_ref: vfs.w02.vf_pc_04_workspace_path_contract_bounded
      source: tracking/collab/stage_02_synthesis/variant_family_seeds/synthesis/principal_synthesis.md
observed_trace_or_eval_evidence:
  - packet_03 eval card for ae_cwd_workdir_path_contract_guard identifies explicit path-invariant logging and reason-code requirements
  - packet_03 closeout marks cwd/workdir surface accepted and usable now
mechanism_claim: preserve cwd/workdir/target-path invariants at every execution step and tool hop to prevent path drift and accidental off-target edits.
target_failure: cwd_path_drift
anti_benchmarkifying_risk: variant may pass by memorizing fixture-relative path patterns instead of generalized path grounding.
expected_improvement: higher deterministic path-fingerprint consistency and fewer target-path mismatches.
expected_failure_mode: strict path normalization can reject legitimate symlink/alias flows and create false negatives.
complexity_cost: medium (path-propagation assertions and invariant fingerprint plumbing).
token_cost_expectation: negligible for deterministic eval; modest log-size growth due to extra path telemetry.
changed_files:
  - blocks/execution/cwd_invariant_loop.py
required_atomic_eval: ae_cwd_workdir_path_contract_guard
required_atomic_eval_status: accepted_packet_03_surface
anticipated_interaction_eval: path_contract_x_workspace_target_integrity_probe
anticipated_interaction_eval_status: blocked_until_packet_05
anticipated_transfer_eval: terminalbench_development_transfer_workspace_path_set_v1
anticipated_transfer_eval_status: anticipated
promotion_threshold: deterministic pass against baseline plus corroboration on sibling path-decoy diagnostics with no increase in off-target touch rate.
retirement_condition: retire if gains are fixture-specific or if transfer reveals brittle behavior outside deterministic fixture layout.
bounded_claims:
  - bounded due Stage 02 workspace-path regime-scoping warnings
  - no claim of universal workspace robustness in packet_04
telemetry_required:
  - cwd_at_step
  - workdir_at_tool_call
  - resolved_target_absolute_path
  - target_hash_match
  - workspace_integrity_summary
model_policy:
  screening_default: oauth:gpt-5.4-mini
  promotion_tier: gpt-5.3-codex
  deterministic_eval_override: no_model
  note: promotion beyond atomic_eligible requires transfer checks due bounded workspace claim.
```

## variant_card: v04_cb_01_decoy_resistant_target_selection

```yaml
variant_id: v04_cb_01_decoy_resistant_target_selection
block_family: ContextBlock
block_interface: ContextBlock.manage(history, new_observation) -> updated_history
source_from_deep_synthesis:
  anchors:
    - claim_ref: mm.w04.explicit_artifact_continuity_workspace_state
      source: tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md
    - claim_ref: mm.w05.cwd_workdir_path_contract
      source: tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md
    - claim_ref: ft.w03.workspace_repo_branch_path_drift
      source: tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md
    - claim_ref: vfs.w02.vf_pc_04_workspace_path_contract_bounded
      source: tracking/collab/stage_02_synthesis/variant_family_seeds/synthesis/principal_synthesis.md
observed_trace_or_eval_evidence:
  - packet_03 eval card for ae_workspace_target_correctness_probe requires target-vs-decoy discrimination with workspace integrity tracking
  - packet_03 closeout marks workspace target correctness accepted and usable now
mechanism_claim: context-state manager should preserve target identity and suppress decoy salience drift under naming/layout perturbations.
target_failure: workspace_target_miss
anti_benchmarkifying_risk: variant can overfit to seen decoy naming patterns while still failing unseen decoy structures.
expected_improvement: lower decoy-touch false positives and higher target-hit stability under fixture perturbations.
expected_failure_mode: over-pruning context may drop legitimate target evidence when tasks require multi-file edits.
complexity_cost: medium (target-candidate ranking logic and context salience filters).
token_cost_expectation: moderate increase for model-backed screening runs due extra target-salience metadata in prompts/logs.
changed_files:
  - blocks/context/full_history.py
  - blocks/context/workspace_target_state.py
  - runner/trace_summary.py
required_atomic_eval: ae_workspace_target_correctness_probe
required_atomic_eval_status: accepted_packet_03_surface
anticipated_interaction_eval: context_targeting_x_tool_result_normalization_probe
anticipated_interaction_eval_status: blocked_until_packet_05
anticipated_transfer_eval: terminalbench_development_transfer_target_selection_set_v1
anticipated_transfer_eval_status: anticipated
promotion_threshold: exceed baseline on target-hit and decoy-touch metrics within declared spread thresholds and pass at least one sibling workspace diagnostic.
retirement_condition: retire if improvements disappear after decoy renaming/layout rotation or if transfer shows task under-completion due context pruning.
bounded_claims:
  - bounded to workspace-target mechanism only
  - no long-horizon memory or recursion claim in first slice
telemetry_required:
  - resolved_target_file_id
  - touched_decoy_file_ids
  - target_candidate_rank_trace
  - workspace_integrity_summary
  - reason_code_distribution
model_policy:
  screening_default: oauth:gpt-5.4-mini
  promotion_tier: gpt-5.3-codex
  deterministic_eval_override: not_applicable
  note: model-backed surface; cheap-model wins alone are insufficient for promotion.
```

## variant_card: v04_tb_01_tool_call_contract_classifier

```yaml
variant_id: v04_tb_01_tool_call_contract_classifier
block_family: ToolBlock
block_interface: ToolBlock.get_tools() -> list[tool_definitions]
source_from_deep_synthesis:
  anchors:
    - claim_ref: mm.w05.tool_gateway_family_separation
      source: tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md
    - claim_ref: mm.w05.permission_policy_vs_capability_boundary
      source: tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md
    - claim_ref: ft.w04.tool_gateway_substrate_mismatch
      source: tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md
    - claim_ref: vfs.w02.vf_pc_05_tool_surface_pruned_standalone
      source: tracking/collab/stage_02_synthesis/variant_family_seeds/synthesis/principal_synthesis.md
observed_trace_or_eval_evidence:
  - packet_03 eval card for ae_tool_call_shape_argument_contract requires strict malformed-call vs runtime-error separation
  - packet_03 closeout marks this tool-call surface accepted and usable now
mechanism_claim: introduce deterministic call-shape classifier to preserve strict argument contract validation and reduce malformed invocation leakage.
target_failure: tool_invocation_error
anti_benchmarkifying_risk: classifier may overfit to known malformed templates and miss semantically malformed but novel payloads.
expected_improvement: fewer false-accept malformed calls; cleaner malformed-vs-runtime attribution in traces.
expected_failure_mode: strict validation may reject backward-compatible or optional-field variants that are semantically valid.
complexity_cost: low_to_medium (schema validator + reason-code harmonization).
token_cost_expectation: negligible for required deterministic gate; possible small prompt reduction from normalized call records.
changed_files:
  - blocks/tools/contract_classifier.py
required_atomic_eval: ae_tool_call_contract_quality_v2
required_atomic_eval_status: packet05a_repaired_surface
anticipated_interaction_eval: tool_call_shape_x_permission_attribution_probe
anticipated_interaction_eval_status: blocked_until_packet_05
anticipated_transfer_eval: terminalbench_development_transfer_tool_contract_set_v1
anticipated_transfer_eval_status: anticipated
promotion_threshold: deterministic contract uplift over baseline plus sibling near-valid camouflage probe pass with stable reason-code mapping.
retirement_condition: retire if uplift depends on fixture-template memorization or if valid-call rejection rises above agreed threshold in transfer checks.
bounded_claims:
  - bounded ablation/support variant only
  - not a standalone tool-family promotion claim due Stage 02 pruning status
telemetry_required:
  - raw_tool_call_payload
  - normalized_tool_call_payload
  - call_shape_classification
  - malformed_vs_runtime_reason_codes
model_policy:
  screening_default: oauth:gpt-5.4-mini
  promotion_tier: gpt-5.3-codex
  deterministic_eval_override: no_model
  note: use strong tier only for survivor confirmation.
```

## variant_card: v04_tb_02_permission_runtime_attribution_split

```yaml
variant_id: v04_tb_02_permission_runtime_attribution_split
block_family: ToolBlock
block_interface: ToolBlock.get_tools() -> list[tool_definitions]
source_from_deep_synthesis:
  anchors:
    - claim_ref: mm.w05.tool_gateway_family_separation
      source: tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md
    - claim_ref: mm.w05.permission_policy_vs_capability_boundary
      source: tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md
    - claim_ref: ft.w04.permission_policy_runtime_mismatch
      source: tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md
    - claim_ref: ft.w04.tool_gateway_substrate_mismatch
      source: tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md
observed_trace_or_eval_evidence:
  - packet_03 eval card for ae_tool_result_normalization_permission_probe requires deny-vs-runtime reason-code separation
  - packet_03 closeout marks tool-result normalization surface accepted and usable now
mechanism_claim: normalize tool results with explicit taxonomy that separates permission denials from runtime/capability faults.
target_failure: permission_policy_runtime_mismatch
anti_benchmarkifying_risk: variant may collapse ambiguous mixed faults into whichever label is rewarded on current fixtures.
expected_improvement: lower reason-code flip-rate and improved attribution stability across deny/runtime paired fixtures.
expected_failure_mode: mixed-fault cases may be misbucketed if taxonomy precedence is too rigid.
complexity_cost: medium (result normalization layer and attribution taxonomy enforcement).
token_cost_expectation: low_to_moderate increase on model-backed runs due richer tool-result metadata.
changed_files:
  - blocks/tools/result_normalizer.py
required_atomic_eval: ae_tool_result_attribution_quality_v2
required_atomic_eval_status: packet05a_repaired_surface
anticipated_interaction_eval: tool_result_attribution_x_workspace_integrity_probe
anticipated_interaction_eval_status: blocked_until_packet_05
anticipated_transfer_eval: terminalbench_development_transfer_tool_attribution_set_v1
anticipated_transfer_eval_status: anticipated
promotion_threshold: beat baseline on attribution consistency and pass sibling deny/runtime perturbation probe without worsening workspace integrity diagnostics.
retirement_condition: retire if attribution gains vanish under adversarial camouflage or if transfer introduces higher unresolved-error rates.
bounded_claims:
  - atomic mechanism claim only in packet_04
  - no universal permission safety claim without later interaction/transfer confirmation
telemetry_required:
  - normalized_output_hash
  - raw_output_link
  - permission_denied_count
  - runtime_error_count
  - reason_code_flip_rate
  - cost_per_accepted_run
model_policy:
  screening_default: oauth:gpt-5.4-mini
  promotion_tier: gpt-5.3-codex
  deterministic_eval_override: not_applicable
  note: gpt-5.3-codex reserved for survivor/tie-break/promotion-strength claims.
```

## variant_card: v04_rb_01_interrupt_retry_spiral_breaker

```yaml
variant_id: v04_rb_01_interrupt_retry_spiral_breaker
block_family: ExecutionBlock
block_interface: ExecutionBlock.run_loop(model, tools, context, max_steps) -> result
mechanism_claim: apply explicit terminal cleanup-order guard behavior on bounded sync-interrupt probe runs to break retry-spiral cleanup blind spots.
target_failure: recovery_loop_or_retry_spiral
changed_files:
  - runner/agent.py
required_atomic_eval: ae_sync_interrupt_cleanup_probe
required_atomic_eval_status: bounded_packet05a_sync_interrupt_l3_upgraded_surface
bounded_claims:
  - bounded diagnostic admission only
  - no promotion authority in packet_05a
```

## variant_card: prompt_plan_env

```yaml
variant_id: prompt_plan_env
block_family: OrientationBlock
block_interface: OrientationBlock.orient(task_prompt, env_info) -> initial_context
changed_files:
  - blocks/orientation/prompt_plan_env.py
```

## variant_card: evidence_report_scaffold

```yaml
variant_id: evidence_report_scaffold
block_family: ContextBlock
block_interface: ContextBlock.manage(history, new_observation) -> updated_history
changed_files:
  - blocks/context/evidence_report_scaffold.py
```
