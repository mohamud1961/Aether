EVAL_BENCHMARK_OUTPUT
- artifact: `failure_taxonomy`
- role: `eval/benchmark analyst`
- preflight_scope_confirmed:
  - Wave 02 eval lane is active and scoped to failure attribution for verifier/grader/replay mismatch, benchmark-contract blindness, false success, and completion/recovery acceptance divergence.
  - This output is failure-taxonomy focused; it does not promote generic benchmark recap or variant-family policy.
  - Evidence precedence used: trajectory verifier artifacts and source code outrank benchmark README prose.
- preflight_planned_read_order:
  - required wave controls and carry-forward controls
  - benchmark captures under `research/sources/benchmarks/`
  - mirrored eval implementations under `research/sources/codebases/deepagents/libs/evals/`
  - local eval surfaces under `evals/`
  - required run bundles for cancel/extract/db-wal mismatch pressure
  - required support dossiers for Wave 02 updates
- preflight_critical_sources_selected:
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
  - `research/sources/benchmarks/src_bnm_8c3b5dc456f5/artifact.txt`
  - `research/sources/benchmarks/src_bnm_e1cfa2bf78c9/artifact.txt`
  - `research/sources/benchmarks/src_bnm_e5f985948a0e/artifact.txt`
  - `research/sources/benchmarks/src_bnm_f6e5d4c3b2a1/artifact.txt`
  - `research/sources/benchmarks/src_bnm_facefeed2020/artifact.txt`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/utils.py`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/external_benchmarks.py`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/llm_judge.py`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/evaluation.py`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/test_tau2_airline.py`
  - `research/sources/codebases/deepagents/libs/evals/deepagents_harbor/langsmith.py`
  - `evals/README.md`
  - `evals/verification_eval.py`
  - `evals/context_eval.py`
  - `evals/step_efficiency_eval.py`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz`
  - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
  - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
  - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd.tar.gz`
  - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz`
  - `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53.tar.gz`
  - `research/analysis/bigai_trace_layer/output/question_answers.json`
- preflight_coverage_risks:
  - `research/sources/benchmarks/` captures are mostly benchmark/readme-level contracts, not full grader implementations.
  - BigAI remains source-missing, so evaluator-mechanism attribution for BigAI is behavioral reconstruction.
  - Local `evals/` files are intent stubs, so local harness evaluation logic is under-evidenced.
- preflight_likely_blind_spots:
  - Hidden BigAI controller policy for verifier invocation and verifier/final-acceptance reconciliation.
  - Full benchmark grader internals for all captured benchmark families beyond mirrored DeepAgents eval code.
  - Recovery-specific replay contracts in local harness code (currently absent from `evals/`).
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
  - `research/sources/benchmarks/src_bnm_8c3b5dc456f5/artifact.txt`
  - `research/sources/benchmarks/src_bnm_e1cfa2bf78c9/artifact.txt`
  - `research/sources/benchmarks/src_bnm_e5f985948a0e/artifact.txt`
  - `research/sources/benchmarks/src_bnm_f6e5d4c3b2a1/artifact.txt`
  - `research/sources/benchmarks/src_bnm_facefeed2020/artifact.txt`
  - `research/sources/codebases/deepagents/libs/evals/README.md`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/README.md`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/utils.py`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/external_benchmarks.py`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/llm_judge.py`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/evaluation.py`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/test_tau2_airline.py`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/runner.py`
  - `research/sources/codebases/deepagents/libs/evals/deepagents_harbor/langsmith.py`
  - `research/sources/codebases/deepagents/libs/evals/deepagents_harbor/failure.py`
  - `evals/README.md`
  - `evals/verification_eval.py`
  - `evals/context_eval.py`
  - `evals/step_efficiency_eval.py`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz`
  - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
  - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
  - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd.tar.gz`
  - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz`
  - `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53.tar.gz`
  - `research/analysis/bigai_trace_layer/output/question_answers.json`
- coverage_not_yet_used:
  - Full benchmark implementation repositories behind the readme captures under `research/sources/benchmarks/src_bnm_*/`.
  - Non-DeepAgents mirrored eval families under `research/sources/codebases/*` not directly tied to the required Wave 02 failure slice.
  - Additional BigAI verifier-heavy slices outside required packet (for example `research/sources/trajectories/BigAI/adaptive-rejection-sampler/**`).
- evidence_classes_touched:
  - `benchmarks`
  - `mirrored codebases`
  - `trajectories`
  - `local eval harness code`
  - `local analysis`
- priority_sources_not_yet_read:
  - benchmark grader internals corresponding to:
    - `research/sources/benchmarks/src_bnm_8c3b5dc456f5/`
    - `research/sources/benchmarks/src_bnm_e1cfa2bf78c9/`
    - `research/sources/benchmarks/src_bnm_e5f985948a0e/`
    - `research/sources/benchmarks/src_bnm_f6e5d4c3b2a1/`
    - `research/sources/benchmarks/src_bnm_facefeed2020/`
  - local harness evaluator implementation beyond stubs in `evals/`.
- support_artifacts_used:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/eval_support_verifier_benchmark_contract_map.md`
- support_artifacts_requested_or_deferred:
  - requested_and_completed:
    - `eval_support_verifier_benchmark_contract_map.md`
  - deferred:
    - none
- coverage_register_updates_needed:
  - Add eval-lane status detail under Wave 02 noting first-pass eval contract mapping complete.
  - Add explicit warning that current benchmark captures are contract-level for several families and should not be read as grader implementation proof.
  - Add explicit mismatch observation: required cancel and extract runs show in-run completion/verifier signaling diverging from bundle-level reward/ctrf outcomes.
- required_dossier_updates:
  - `tracking/collab/stage_02_synthesis/eval_benchmark_dossiers/verification_completion_and_recovery.md`
  - `tracking/collab/stage_02_synthesis/eval_benchmark_dossiers/verification_completion_recovery_failures.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/verification_and_replay.md`
  - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/verification_completion_recovery_failures.md`
- benchmark_contracts:
  - claim: `TerminalBench-like acceptance in required runs is bundle-verifier anchored, not narrative anchored.`
    observation:
      - Required run artifacts expose acceptance through verifier outputs (`reward.txt`, `ctrf.json`, pytest traces), and failures are explicit despite success narratives in trajectories.
    inference:
      - Failure taxonomy should treat bundle verifier output as final acceptance layer above in-run completion statements.
    confidence: high
    evidence_paths:
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz`
      - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd.tar.gz`
  - claim: `Captured benchmark pages in this wave mostly provide contract intent and setup constraints, not runnable grader internals.`
    observation:
      - Benchmark captures are repository/web summaries and leaderboard/setup text.
    inference:
      - Claims about grader implementation must be sourced from code paths (for this wave: DeepAgents eval code), not benchmark page prose.
    confidence: high
    evidence_paths:
      - `research/sources/benchmarks/src_bnm_e5f985948a0e/artifact.txt`
      - `research/sources/benchmarks/src_bnm_8c3b5dc456f5/artifact.txt`
      - `research/sources/benchmarks/src_bnm_e1cfa2bf78c9/artifact.txt`
      - `research/sources/benchmarks/src_bnm_f6e5d4c3b2a1/artifact.txt`
      - `research/sources/benchmarks/src_bnm_facefeed2020/artifact.txt`
- grader_and_verifier_patterns:
  - claim: `DeepAgents eval stack separates hard correctness gates, replay/state gates, and judge-style grading.`
    observation:
      - `.success(...)` assertions hard-fail correctness; `.expect(...)` logs diagnostics only.
      - External BFCL scoring replays ground-truth calls and diffs model-vs-reference API state.
      - Tau2 scoring computes `reward = db_score * communicate_score` with success requiring both perfect scores.
      - LLM judge wraps prompt criteria and logs aggregate result.
    inference:
      - Wave 02 failures can be attributed to distinct evaluator layers rather than one generic verifier failure.
    confidence: high
    evidence_paths:
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/utils.py`
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/external_benchmarks.py`
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/evaluation.py`
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/test_tau2_airline.py`
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/llm_judge.py`
  - claim: `Reward projection can introduce false-zero aggregation when verifier artifacts are absent.`
    observation:
      - Harbor feedback extraction returns fallback `0.0` for missing `verifier_result` or missing reward key.
    inference:
      - Failure attribution needs to distinguish `missing verifier artifact` from explicit verifier fail to avoid misclassification.
    confidence: high
    evidence_paths:
      - `research/sources/codebases/deepagents/libs/evals/deepagents_harbor/langsmith.py`
- replay_or_reproducibility_notes:
  - claim: `Replay/state reconstruction is explicitly implemented for selected benchmark families and should remain separate from transcript-level scoring.`
    observation:
      - BFCL and tau2 code replay actions or expected state on fresh environments; conversation runner collects transcript but success is computed by replay/state checks.
    inference:
      - `replay/grader mismatch` is a real Wave 02 family, not a side effect of prompt quality alone.
    confidence: high
    evidence_paths:
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/external_benchmarks.py`
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/evaluation.py`
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/runner.py`
- gaming_or_proxy_risks:
  - claim: `Substring and criterion-judge paths create fake-good risk when treated as sufficient proof.`
    observation:
      - FRAMES/NEXUS text scoring uses normalized snippet presence.
      - LLM judge depends on rubric prompt and model behavior.
      - Local harness `evals/` does not yet implement concrete verifier logic.
    inference:
      - Benchmark-contract blindness risk is high if local acceptance depends on narrative or proxy checks without artifact/state gates.
    confidence: high
    evidence_paths:
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/external_benchmarks.py`
      - `research/sources/codebases/deepagents/libs/evals/tests/evals/llm_judge.py`
      - `evals/verification_eval.py`
      - `evals/context_eval.py`
      - `evals/step_efficiency_eval.py`
  - claim: `Required Wave 02 runs concretely show local/verifier-narrative success that does not survive benchmark contract checks.`
    observation:
      - BigAI `98b7...` and deepagents `ca5a...` both fail `test_tasks_cancel_above_max_concurrent` with reward `0` despite local verified-success narratives.
      - KIRA extract run fails similarity threshold (65.38% < 90%) with reward `0` despite completion pressure in trajectory.
      - BigAI extract run lacks `finish_verification` call in trajectory while bundle acceptance is failing.
    inference:
      - Promote dedicated failure families for `false-success due to weak completion contract` and `verifier/grader/final-acceptance mismatch`.
    confidence: high
    evidence_paths:
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz`
      - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
      - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd.tar.gz`
      - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
- upstream_artifact_implications:
  - `failure_taxonomy`:
    - keep separate cards for:
      - verifier omission/absence in high-risk regimes
      - false completion from local-check sufficiency gaps
      - replay/grader/final acceptance mismatch
      - recovery failure from environment-state invalidation vs task-logic failure
  - `mechanism_map` carry-forward check:
    - preserve anti-collapse rule that verifier pass is not equivalent to run success.
  - `eval_implications` handoff:
    - require evaluator instrumentation that logs per-layer outcomes `{inline checks, verifier artifacts, replay/state grade, judge grade, final reward}`.
- contradiction_notes:
  - contradiction:
    observation:
      - BigAI has verifier-rich traces and also documented verifier-pass/overall-fail divergence in local synthesis artifacts.
    inference:
      - Treat BigAI evaluator attribution as `behavioral reconstruction`; do not promote source-level causal claims.
    confidence: medium
    evidence_paths:
      - `research/analysis/bigai_trace_layer/output/question_answers.json`
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
  - contradiction:
    observation:
      - KIRA db-wal required run failure surface includes infrastructure/cwd invalidation and timeout signals while task demands data-recovery correctness.
    inference:
      - Keep mixed attribution (`environment + orchestration + completion/recovery policy`) rather than pure algorithmic-recovery failure.
    confidence: medium
    evidence_paths:
      - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz`
      - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
- confidence_notes:
  - high confidence:
    - DeepAgents eval-layer separation and replay/state grading claims (source code direct).
    - Required cancel/extract mismatch claims with direct bundle verifier evidence.
    - Harbor reward-fallback behavior claim.
  - medium confidence:
    - BigAI evaluator mechanism interpretation (`behavioral reconstruction` only).
    - KIRA db-wal root-cause layering because visible run is single-instance and infrastructure-heavy.
  - low confidence:
    - none promoted.
- open_questions:
  - Which missing benchmark implementation repos should be mirrored first to reduce README-level contract blindness for Wave 02 follow-up?
  - In required cancellation failures, are BigAI/deepagents failing for the same semantic cleanup reason or different scheduler/runtime behaviors?
  - Should fallback `0.0` for missing verifier artifacts be split into a distinct score key to prevent conflation with explicit test failures?
- next_hand_off_target:
  - `contradiction analyst` for cross-lane anti-collapse check on verifier/grader/replay/final-acceptance layering.
  - `principal synthesis` for promotion of Wave 02 failure families with explicit mixed-cause boundaries.
