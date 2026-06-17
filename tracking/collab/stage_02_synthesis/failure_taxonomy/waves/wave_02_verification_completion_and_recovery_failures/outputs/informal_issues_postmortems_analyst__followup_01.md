INFORMAL_ISSUES_POSTMORTEMS_OUTPUT
- artifact: failure_taxonomy / wave_02_verification_completion_and_recovery_failures
- role: informal/issues/postmortems analyst
- preflight_scope_confirmed:
  - Scope confirmed as contradiction-pressure attribution for verification/completion/recovery failures.
  - This follow-up does not recast informal incident reports as source-backed mechanism proof.
  - Layer separation preserved: completion signal, verifier/grader/replay/final acceptance, and recovery/resume state are treated as distinct surfaces.
- preflight_planned_read_order:
  - Wave controls first: Wave 02 brief, support-subagent rules, outputs README, artifact decision, cumulative synthesis, coverage register, phase/wave plan, lane closure criteria, Wave 01 adjudication, mechanism-map Wave 03 principal synthesis.
  - Corpus integrity anchor: captured-for-synthetic-prep manifest.
  - Incident-heavy issue captures for false completion, stuck non-terminal state, resume/index drift, transcript-size resume failure, restore/rewind correctness/security.
  - Postmortem/informal captures for operator doctrine and benchmark-contract mismatch pressure.
- preflight_critical_sources_selected:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/brief.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - `research/sources/issues/src_iss_5d861db09829/artifact.txt`
  - `research/sources/issues/src_iss_6ba217fff208/artifact.txt`
  - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
  - `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`
  - `research/sources/issues/src_iss_222a58240294/artifact.txt`
  - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
  - `research/sources/issues/src_iss_da41417f5655/artifact.txt`
  - `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt`
  - `research/sources/issues/src_iss_a1a5a26e92ab/artifact.txt`
  - `research/sources/issues/src_iss_a1b2c3d4e5f6/artifact.txt`
  - `research/sources/issues/src_iss_f07284ab370e/artifact.txt`
  - `research/sources/issues/src_iss_f44f83f3fbc3/artifact.txt`
  - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`
  - `research/sources/postmortems/src_pmt_ca79e818d699/artifact.txt`
  - `research/sources/informal/cursor_long_running_agents.md`
  - `research/sources/informal/cursor_cursorbench.md`
  - `research/sources/informal/openai_evmbench.md`
  - `research/sources/informal/openai_monitor_misalignment.md`
  - `research/sources/informal/langchain_anatomy_of_harness.md`
- preflight_coverage_risks:
  - Issue captures are mostly single-snapshot text exports with uneven maintainer follow-through and weak closure provenance.
  - Several postmortem captures are mixed-quality: one empty (`src_pmt_2c716b81f9a5`) and one ad-heavy/low-credibility (`src_pmt_afc13590bd50`).
  - Informal product posts include performance and quality claims without raw failure denominators.
- preflight_likely_blind_spots:
  - Cross-vendor prevalence outside the captured issue set and products represented in this corpus slice.
  - Longitudinal fix durability after issue closure.
  - Direct grader/replay implementation internals (owned by eval/codebase lanes).
- preflight_blockers:
  - none
- coverage_used:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/brief.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/inputs/support_subagent_rules.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/README.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_PHASE_AND_WAVE_OPERATING_PLAN.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/adjudication/checklist_adjudicator.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - `research/sources/issues/src_iss_5d861db09829/artifact.txt`
  - `research/sources/issues/src_iss_6ba217fff208/artifact.txt`
  - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
  - `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`
  - `research/sources/issues/src_iss_222a58240294/artifact.txt`
  - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
  - `research/sources/issues/src_iss_da41417f5655/artifact.txt`
  - `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt`
  - `research/sources/issues/src_iss_a1a5a26e92ab/artifact.txt`
  - `research/sources/issues/src_iss_b5d3d874490a/artifact.txt`
  - `research/sources/issues/src_iss_f44f83f3fbc3/artifact.txt`
  - `research/sources/issues/src_iss_e88081f909bc/artifact.txt`
  - `research/sources/issues/src_iss_f07284ab370e/artifact.txt`
  - `research/sources/issues/src_iss_31cf9134cefa/artifact.txt`
  - `research/sources/issues/src_iss_51e11ab8bc0e/artifact.txt`
  - `research/sources/issues/src_iss_7ea08b4fb93c/artifact.txt`
  - `research/sources/issues/src_iss_d3818cf54a20/artifact.txt`
  - `research/sources/issues/src_iss_a1b2c3d4e5f6/artifact.txt`
  - `research/sources/postmortems/src_pmt_2c716b81f9a5/artifact.txt`
  - `research/sources/postmortems/src_pmt_350e236460b0/artifact.txt`
  - `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt`
  - `research/sources/postmortems/src_pmt_afc13590bd50/artifact.txt`
  - `research/sources/postmortems/src_pmt_ca79e818d699/artifact.txt`
  - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`
  - `research/sources/informal/cursor_long_running_agents.md`
  - `research/sources/informal/cursor_self_driving_codebases.md`
  - `research/sources/informal/cursor_dynamic_context_discovery.md`
  - `research/sources/informal/cursor_agent_sandboxing.md`
  - `research/sources/informal/cursor_cursorbench.md`
  - `research/sources/informal/openai_evmbench.md`
  - `research/sources/informal/openai_monitor_misalignment.md`
  - `research/sources/informal/langchain_anatomy_of_harness.md`
  - `research/sources/informal/langchain_agent_observability.md`
  - `research/sources/informal/langchain_autonomous_context.md`
  - `research/sources/informal/humanlayer_12_factor_agents.md`
  - `research/sources/informal/cognition_closing_agent_loop.md`
  - `research/sources/informal/anthropic_long_running_harness.md`
  - `research/sources/informal/cursor_self_summarization.md`
  - `research/sources/informal/cursor_building_bugbot.md`
- coverage_not_yet_used:
  - `research/sources/issues/src_iss_*.txt` files not enumerated above (remaining captured issue set).
  - `research/sources/informal/x_*.md` social captures not read in this follow-up.
  - `research/sources/trajectories/**` and benchmark bundle internals (owned by trajectory/eval lanes for direct behavior proof).
  - `research/sources/benchmarks/**` and eval/codebase implementation surfaces (owned by eval/codebase lanes).
- evidence_classes_touched:
  - wave governance/control artifacts
  - issues
  - postmortems
  - informal engineering writeups
- priority_sources_not_yet_read:
  - `research/sources/issues/src_iss_62f4e8001a9d/artifact.txt`
  - `research/sources/issues/src_iss_677a876a6ea9/artifact.txt`
  - `research/sources/issues/src_iss_809077092a02/artifact.txt`
  - `research/sources/issues/src_iss_bfc82053a70d/artifact.txt`
  - `research/sources/issues/src_iss_c684343ec3ff/artifact.txt`
  - `research/sources/informal/cognition_agent_trace.md`
  - `research/sources/informal/cursor_bugbot_autofix.md`
- support_artifacts_used:
  - none
- support_artifacts_requested_or_deferred:
  - deferred `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_support_false_completion_recovery_cluster.md` because this follow-up stayed within bounded direct-source clustering.
- coverage_register_updates_needed:
  - add that informal lane follow-up increased confidence for existence of `false_completion`, `resume_index_drift`, and `non_terminal_recovery_limbo` pressure clusters.
  - preserve caution that causal ownership remains mixed and primarily issue-reported in this lane.
  - keep benchmark-contract attribution as unresolved pending direct eval/codebase evidence.
- required_dossier_updates:
  - updated: `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/verification_completion_recovery_failures.md`
  - updated: `tracking/collab/stage_02_synthesis/eval_benchmark_dossiers/verification_completion_recovery_failures.md`
- high_signal_operating_claims:
  - claim_id: FT_W02_INF_FU1_false_completion_without_target_proof
    observation:
      - Multiple incidents report completion states asserted from host-side command success while target-side execution or persisted runtime events were absent.
    inference:
      - False completion pressure is not only model mistake; it is a completion/verification contract failure where “done” semantics are too weak.
    confidence: medium
    weakener:
      - strongest examples are user-reported and not independently replayed in this lane.
    evidence_paths:
      - `research/sources/issues/src_iss_5d861db09829/artifact.txt`
      - `research/sources/issues/src_iss_6ba217fff208/artifact.txt`
      - `research/sources/postmortems/src_pmt_ca79e818d699/artifact.txt`

  - claim_id: FT_W02_INF_FU2_resume_index_and_context_drift
    observation:
      - Resume failures recur as stale/missing session indexes, older checkpoint selection, and transcript-volume parsing failures.
    inference:
      - Recovery reliability depends on durable state indexing and transcript compaction/serialization discipline, not just restart mechanics.
    confidence: high
    weakener:
      - incidents concentrate in a subset of products and operating environments.
    evidence_paths:
      - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
      - `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`
      - `research/sources/issues/src_iss_222a58240294/artifact.txt`
      - `research/sources/issues/src_iss_a1b2c3d4e5f6/artifact.txt`

  - claim_id: FT_W02_INF_FU3_non_terminal_recovery_limbo
    observation:
      - Crash/interruption cases repeatedly describe sessions stuck in running/thinking-like states with queued input but no progress.
    inference:
      - Explicit terminal-state reconciliation is a distinct recovery control; without it, completion and recovery layers deadlock.
    confidence: high
    weakener:
      - some incidents are extension/runtime-specific and may not generalize to all harnesses.
    evidence_paths:
      - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
      - `research/sources/issues/src_iss_da41417f5655/artifact.txt`
      - `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt`

  - claim_id: FT_W02_INF_FU4_rewind_restore_is_secondary_failure_surface
    observation:
      - Rewind/restore paths are reported as nullifying initial state, lacking branch coverage, and in one case exposing unsafe deserialization risk.
    inference:
      - Recovery mechanisms themselves form mixed correctness + security failure pressure, not only mitigation infrastructure.
    confidence: medium
    weakener:
      - part of evidence is feature/task proposals and security review claims rather than confirmed exploited incidents.
    evidence_paths:
      - `research/sources/issues/src_iss_a1a5a26e92ab/artifact.txt`
      - `research/sources/issues/src_iss_b5d3d874490a/artifact.txt`
      - `research/sources/issues/src_iss_f44f83f3fbc3/artifact.txt`
      - `research/sources/issues/src_iss_e88081f909bc/artifact.txt`

  - claim_id: FT_W02_INF_FU5_recovery_quality_depends_on_error_contract
    observation:
      - Tool/runtime failures are often surfaced as unstructured strings; requests for typed error category + recoverability hints recur.
    inference:
      - Weak error contracts likely amplify retry loops and silent stalls by preventing reliable recovery branching.
    confidence: medium
    weakener:
      - this lane cannot quantify downstream failure-rate reduction from structured errors.
    evidence_paths:
      - `research/sources/issues/src_iss_f07284ab370e/artifact.txt`
      - `research/sources/issues/src_iss_d3818cf54a20/artifact.txt`
      - `research/sources/issues/src_iss_31cf9134cefa/artifact.txt`
      - `research/sources/informal/langchain_anatomy_of_harness.md`
- issue_and_postmortem_findings:
  - cluster: completion_claim_without_verifiable_outcome
    observation:
      - completion can be declared when only local or intermediate milestones are satisfied.
    mixed_cause_surface:
      - harness completion policy
      - verifier omission
      - benchmark-contract ambiguity
    evidence:
      - `research/sources/issues/src_iss_5d861db09829/artifact.txt`
      - `research/sources/issues/src_iss_6ba217fff208/artifact.txt`

  - cluster: resume_and_index_integrity_breakdown
    observation:
      - recoverability fails despite preserved logs due to index staleness, snapshot drift, and oversized transcript rows.
    mixed_cause_surface:
      - persistence/index design
      - compaction policy
      - parser robustness
    evidence:
      - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
      - `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`
      - `research/sources/issues/src_iss_222a58240294/artifact.txt`

  - cluster: crash_non_terminalization
    observation:
      - after crashes, sessions remain in live-like states lacking terminal markers, blocking normal continuation.
    mixed_cause_surface:
      - runtime state machine
      - crash recovery orchestration
      - session finalization policy
    evidence:
      - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
      - `research/sources/issues/src_iss_da41417f5655/artifact.txt`
      - `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt`

  - cluster: restore_path_correctness_and_security
    observation:
      - restoration surfaces include both correctness regressions and possible deserialization attack surface.
    mixed_cause_surface:
      - recovery implementation quality
      - test/coverage debt
      - state integrity/security design
    evidence:
      - `research/sources/issues/src_iss_a1a5a26e92ab/artifact.txt`
      - `research/sources/issues/src_iss_b5d3d874490a/artifact.txt`
      - `research/sources/issues/src_iss_f44f83f3fbc3/artifact.txt`
- contradiction_or_support_notes:
  - contradiction:
    - Product and research writeups emphasize long-horizon reliability and autonomous completion, while issue evidence repeatedly documents resume drift, stuck-state recovery failure, and false completion.
    - evidence_paths:
      - `research/sources/informal/cursor_long_running_agents.md`
      - `research/sources/informal/anthropic_long_running_harness.md`
      - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
      - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
  - support:
    - Informal guidance on dynamic context and compaction aligns with issue reports where transcript size and stale compression/indexing correlate with resume failures.
    - evidence_paths:
      - `research/sources/informal/cursor_dynamic_context_discovery.md`
      - `research/sources/informal/langchain_autonomous_context.md`
      - `research/sources/issues/src_iss_222a58240294/artifact.txt`
  - support_with_boundary:
    - Eval writeups stress mismatch between offline grader signals and developer-perceived success, supporting benchmark-contract blindness pressure, but this remains methodological pressure rather than direct causal proof in this lane.
    - evidence_paths:
      - `research/sources/informal/cursor_cursorbench.md`
      - `research/sources/informal/openai_evmbench.md`
- unvalidated_leads:
  - Measure whether typed error recoverability metadata reduces retry thrash and silent-stall incidence.
  - Add synthetic fault-injection tests for “crash during in-flight reasoning item” and verify automatic terminalization.
  - Compare fixed-threshold compaction vs model-driven compaction on resume consistency and stale-context rates.
- confidence_notes:
  - high confidence:
    - existence of the major pressure clusters (`false_completion`, `resume/index drift`, `non_terminal_recovery_limbo`) from repeated issue evidence.
  - medium confidence:
    - cross-system prevalence and dominant root-cause attribution due to issue-heavy evidence and limited closure data.
  - low-confidence material handling:
    - `src_pmt_2c716b81f9a5` is empty and not used for claims.
    - `src_pmt_afc13590bd50` is ad-heavy mixed content and treated as low-credibility background only.
- open_questions:
  - What minimum completion contract prevents host-side success from being misreported as task success?
  - Which recovery incidents are primarily harness bugs versus environment/substrate faults?
  - What replay/grader/final-acceptance mismatch rates remain after enforcing explicit terminal-state reconciliation?
- next_hand_off_target:
  - contradiction analyst and principal synthesis for mixed-cause adjudication and saturation assignment.
