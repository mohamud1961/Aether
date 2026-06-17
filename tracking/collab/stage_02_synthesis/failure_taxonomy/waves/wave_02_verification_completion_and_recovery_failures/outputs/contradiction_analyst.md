DEEP_SYNTHESIS_CONTRADICTION_OUTPUT
- artifact: `failure_taxonomy/wave_02_verification_completion_and_recovery_failures`
- overall_verdict: `pass_with_warnings`

- preflight_scope_confirmed:
  - Reviewed Wave 02 as a verification/completion/recovery failure-attribution wave, not as a mechanism recap.
  - Enforced the required anti-collapse split across inline proof, verifier, grader/replay, final acceptance, cleanup, and recovery/resume.
  - Enforced wave boundary: wave acceptability is not artifact completion.

- preflight_planned_read_order:
  - Required packet control surfaces first (brief/output manifest/decision/cumulative synthesis/coverage register/Wave 01 adjudication/mechanism-map Wave 03 synthesis).
  - All five first-pass lane outputs.
  - Materially cited support outputs.
  - Direct spot-check of required high-impact trajectory + bundle artifacts for mismatch/recovery claims.

- preflight_critical_sources_selected:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/brief.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/README.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/adjudication/checklist_adjudicator.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/trajectory_failure_analyst.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/codebase_source_reconstruction_analyst.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/literature_papers_docs_analyst.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_issues_postmortems_analyst.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/eval_benchmark_analyst.md`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz`
  - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
  - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
  - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd.tar.gz`
  - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/utils.py`
  - `research/sources/codebases/deepagents/libs/evals/deepagents_harbor/langsmith.py`
  - `runner/evaluator.py`
  - `blocks/verification/trust_model.py`
  - `evals/verification_eval.py`

- preflight_coverage_risks:
  - Benchmark captures under `research/sources/benchmarks/src_bnm_*/artifact.txt` are mostly repository/readme snapshots rather than grader-internal code.
  - BigAI remains no-source; mechanism attribution beyond behavior is still unavailable.
  - Recovery root-cause isolation for KIRA `db-wal-recovery` is still dominated by a single required run.
  - Extract-task coverage remains thin on deepagents (aborted run with 2-step trajectory).

- preflight_likely_blind_spots:
  - BigAI controller policy for verifier invocation and verifier-pass/final-fail reconciliation.
  - Full grader implementation details for benchmark captures not mirrored as code in this wave.
  - Cross-run reproducibility for KIRA cwd-invalidation failure mode.

- preflight_blockers:
  - none

- coverage_used:
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/brief.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/README.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/adjudication/checklist_adjudicator.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/trajectory_failure_analyst.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/codebase_source_reconstruction_analyst.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/literature_papers_docs_analyst.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_issues_postmortems_analyst.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_issues_postmortems_analyst__followup_01.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/eval_benchmark_analyst.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/trajectory_support_false_completion_matrix.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/trajectory_support_recovery_failure_matrix.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/codebase_support_verifier_recovery_failure_map.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/codebase_support_completion_cleanup_map.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/literature_support_verification_recovery_failure_cluster.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/eval_support_verifier_benchmark_contract_map.md`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz`
  - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
  - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
  - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd.tar.gz`
  - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz`
  - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
  - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8.tar.gz`
  - `research/sources/benchmarks/src_bnm_8c3b5dc456f5/artifact.txt`
  - `research/sources/benchmarks/src_bnm_e1cfa2bf78c9/artifact.txt`
  - `research/sources/benchmarks/src_bnm_e5f985948a0e/artifact.txt`
  - `research/sources/benchmarks/src_bnm_f6e5d4c3b2a1/artifact.txt`
  - `research/sources/benchmarks/src_bnm_facefeed2020/artifact.txt`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/utils.py`
  - `research/sources/codebases/deepagents/libs/evals/deepagents_harbor/langsmith.py`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/evaluation.py`
  - `runner/evaluator.py`
  - `blocks/verification/trust_model.py`
  - `evals/verification_eval.py`

- coverage_not_yet_used:
  - Full benchmark grader implementation repositories corresponding to `research/sources/benchmarks/src_bnm_*/` captures.
  - Additional BigAI verifier-heavy slices outside required packet (for example `research/sources/trajectories/BigAI/adaptive-rejection-sampler/**`).
  - Additional KIRA `db-wal-recovery` runs to test cwd-invalidation reproducibility.
  - Any local harness verifier/recovery implementation beyond current stub files.

- evidence_classes_touched:
  - `trajectories`
  - `benchmark captures`
  - `mirrored codebases`
  - `papers`
  - `docs`
  - `issues`
  - `postmortems`
  - `informal sources`
  - `local harness code`
  - `local analysis` (`bigai_trace_layer` via lane outputs)
  - `wave governance/control artifacts`

- priority_sources_not_yet_read:
  - Grader-internal code for benchmark captures under:
    - `research/sources/benchmarks/src_bnm_8c3b5dc456f5/`
    - `research/sources/benchmarks/src_bnm_e1cfa2bf78c9/`
    - `research/sources/benchmarks/src_bnm_e5f985948a0e/`
    - `research/sources/benchmarks/src_bnm_f6e5d4c3b2a1/`
    - `research/sources/benchmarks/src_bnm_facefeed2020/`
  - Additional direct trajectories for:
    - `research/sources/trajectories/terminus-kira/db-wal-recovery/**`
    - `research/sources/trajectories/BigAI/extract-moves-from-video/**`

- support_artifact_gaps:
  - Missing support output declared in Wave 02 README:
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_support_false_completion_recovery_cluster.md`
  - This is a support-track gap, not a structural blocker for current wave-level contradiction verdict.

- support_artifacts_used:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/trajectory_support_false_completion_matrix.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/trajectory_support_recovery_failure_matrix.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/codebase_support_verifier_recovery_failure_map.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/codebase_support_completion_cleanup_map.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/literature_support_verification_recovery_failure_cluster.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/eval_support_verifier_benchmark_contract_map.md`

- support_artifacts_requested_or_deferred:
  - Deferred:
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_support_false_completion_recovery_cluster.md`
  - No additional support artifacts were requested during this contradiction pass.

- coverage_register_consistency:
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md` is stale relative to on-disk Wave 02 outputs.
  - Register currently emphasizes trajectory-lane first-pass status, but codebase/literature/informal/eval first-pass outputs now exist under wave outputs.
  - Register correctly preserves that no Wave 02 family is decision-ready.

- coverage_register_updates_needed:
  - Update Wave 02 lane-progress section to reflect first-pass outputs for `trajectory`, `codebase`, `literature`, `informal`, and `eval` lanes.
  - Preserve explicit warning that benchmark-contract evidence remains partially contract-level (README/snapshot-heavy) pending direct grader implementation reads.
  - Preserve explicit warning that no Wave 02 failure family is `decision_ready`.

- required_dossier_updates:
  - Confirm and keep synchronized with Wave 02 lane claims:
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/verification_and_replay.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/checkpoint_restore_and_resumability.md`
    - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/verification_completion_recovery_failures.md`
    - `tracking/collab/stage_02_synthesis/eval_benchmark_dossiers/verification_completion_and_recovery.md`
    - `tracking/collab/stage_02_synthesis/eval_benchmark_dossiers/verification_completion_recovery_failures.md`

- supported_findings:
  - finding_id: `S1_false_completion_with_verifier_or_narrative_success_but_failed_final_gate`
    observation:
      - BigAI `98b7...` shows `finish_verification` + `verification_result_status: PASSED` in trajectory.
      - Bundle verifier still reports reward `0` with failed `test_tasks_cancel_above_max_concurrent`.
      - deepagents `ca5a...` shows analogous local verification narrative with same failing edge-case test and reward `0`.
    inference:
      - Wave 02 has direct evidence for a real verifier/narrative-success versus final-acceptance mismatch family.
    confidence: high
    evidence_paths:
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz`

  - finding_id: `S2_verifier_omission_and_completion_pressure_in_extract_regime`
    observation:
      - BigAI extract trajectory `953d...` has no visible `finish_verification` or verifier status events.
      - KIRA extract trajectory `3df8...` shows repeated completion pressure while bundle verifier fails similarity threshold (65.38% < 90%, reward `0`).
    inference:
      - Verifier omission and weak completion closure are both active paths to false completion in extraction-heavy tasks.
    confidence: medium
    weakener:
      - BigAI extract inference is currently from one readable required trajectory.
    evidence_paths:
      - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
      - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
      - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd.tar.gz`

  - finding_id: `S3_recovery_breakdown_includes_environment_state_invalidations`
    observation:
      - KIRA `db-wal-recovery` bundle shows reward `0`, timeout/exception surfaces, and `getcwd: cannot access parent directories` errors.
    inference:
      - Recovery failures in this wave are not purely algorithmic repair misses; environment/runtime state invalidation is also load-bearing.
    confidence: medium
    weakener:
      - Current evidence is concentrated in one required KIRA run.
    evidence_paths:
      - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz`

  - finding_id: `S4_eval_layer_separation_is_source_visible`
    observation:
      - DeepAgents eval code distinguishes hard-fail assertions (`success`) from non-failing expectations (`expect`), and Harbor reward extraction falls back to `0.0` when verifier payload is missing/malformed.
    inference:
      - Wave 02 attribution should continue separating inline checks, verifier outputs, and reward projection; missing verifier artifacts can otherwise be conflated with explicit failure.
    confidence: high
    evidence_paths:
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/utils.py`
      - `research/sources/codebases/deepagents/libs/evals/deepagents_harbor/langsmith.py`

- unsupported_or_overclaimed_findings:
  - overclaim_id: `O1_benchmark_contract_claims_as_if_grader_internals_are_covered`
    issue:
      - Benchmark-contract analysis is materially improved, but many cited benchmark sources are repository/readme captures, not grader code internals.
    consequence:
      - Stronger causal claims about benchmark-contract blindness should remain bounded unless grader implementations are mirrored/read directly.
    evidence_paths:
      - `research/sources/benchmarks/src_bnm_8c3b5dc456f5/artifact.txt`
      - `research/sources/benchmarks/src_bnm_e1cfa2bf78c9/artifact.txt`
      - `research/sources/benchmarks/src_bnm_e5f985948a0e/artifact.txt`
      - `research/sources/benchmarks/src_bnm_f6e5d4c3b2a1/artifact.txt`
      - `research/sources/benchmarks/src_bnm_facefeed2020/artifact.txt`

  - overclaim_id: `O2_recovery_root_cause_specificity_for_kira_db_wal`
    issue:
      - Evidence supports environment/runtime failure pressure, but assigning dominant root cause remains underpowered with a single run.
    evidence_paths:
      - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz`

  - overclaim_id: `O3_control_surface_currency`
    issue:
      - Coverage register state lags observed lane completion and should not be treated as current without update.
    evidence_paths:
      - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
      - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/*.md`

- missing_evidence_classes:
  - none at minimum class level for this wave gate (trajectory/source/literature/informal/eval classes are all present).
  - remaining gap is depth within benchmark-contract evidence (grader internals), not total class absence.

- reconciliation_failures:
  - Benchmark-contract blindness remains only partially reconciled because eval lane currently joins trajectory mismatches with DeepAgents eval code, but benchmark captures are still largely contract-level prose.
  - Recovery causality remains mixed and unresolved for KIRA db-wal between environment instability and harness-policy effects.

- coverage_blind_spots:
  - Thin extract-task trajectory depth in non-KIRA families (deepagents run aborted; BigAI extract thin).
  - BigAI still no-source (behavioral reconstruction boundary persists).
  - Missing informal support cluster artifact in Wave 02 outputs.

- required_repairs_before_acceptance:
  - Update `tracking/collab/stage_02_synthesis/coverage_register/current_status.md` so Wave 02 lane status reflects all current first-pass outputs.
  - Either produce or explicitly retire with rationale:
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_support_false_completion_recovery_cluster.md`
  - Keep Wave 02 failure-family confidence bounded (no decision-ready promotion) until additional benchmark grader internals and cross-run recovery checks are read.

- optional_pressure_tests:
  - Add additional KIRA `db-wal-recovery` runs to test reproducibility of cwd-invalidated recovery failure.
  - Add more extraction-family trajectories (especially BigAI/deepagents) to disambiguate verifier omission versus capture-format omission.
  - Mirror and read at least one benchmark grader implementation corresponding to a currently read `src_bnm_*` capture.

- gate_review_recommendations:
  - Wave 02 can proceed as `pass_with_warnings` for principal synthesis under explicit uncertainty bounds.
  - Preserve explicit anti-collapse language in principal synthesis: inline proof, verifier, replay/grader, and final acceptance are distinct layers.
  - Maintain statement that accepted Wave 02 is not `failure_taxonomy` completion.

- confidence: medium-high
