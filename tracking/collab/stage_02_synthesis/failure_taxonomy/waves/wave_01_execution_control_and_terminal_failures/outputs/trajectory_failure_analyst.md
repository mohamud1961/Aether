TRAJECTORY_FAILURE_OUTPUT
- artifact: failure_taxonomy / wave_01_execution_control_and_terminal_failures
- role: trajectory/failure analyst
- preflight_scope_confirmed:
  - This wave is treated as a failure-domain pass, not a mechanism recap. The lane centers execution-control loss, terminal-grounding loss, process lifecycle failures, timeout/stall pressure, and false-success/repo-state drift attribution.
  - This output is trajectory-first and keeps implementation claims separate from source-backed fact. BigAI remains explicitly `behavioral reconstruction`.
  - The optional eval/benchmark fifth lane remains inactive for this lane output because required trajectory evidence is sufficient for first-pass failure attribution in-scope; reactivation is reserved for claims requiring grader/replay contract internals.
  - Control surfaces read before synthesis include `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/brief.md`, `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/inputs/support_subagent_rules.md`, `tracking/collab/stage_02_synthesis/failure_taxonomy/brief.md`, `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`, `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`, `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`.
- preflight_planned_read_order:
  - 1. Wave packet controls and carry-forward cautions.
  - 2. Required triad trajectories for `extract-moves-from-video`, `cancel-async-tasks`, and `db-wal-recovery` across `deepagents`, `terminus-kira`, and `BigAI`.
  - 3. Required BigAI local analysis pressure: `research/analysis/bigai_trace_layer/output/answered_questions.md`.
  - 4. Required missing case-study pressure: `headless-terminal` triad trajectories.
  - 5. Build support artifacts for failure timeline and terminal failure matrix, then synthesize attribution with explicit uncertainty.
- preflight_critical_sources_selected:
  - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
  - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
  - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
  - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
  - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
  - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
  - `research/analysis/bigai_trace_layer/output/answered_questions.md`
- preflight_coverage_risks:
  - `extract-moves-from-video` remains evidence-thin for completion attribution because DeepAgents aborts early and the inspected BigAI slice does not show a visible terminal verifier closure.
  - `terminus-kira/db-wal-recovery` is strongly failure-heavy but still a single visible run slice; prevalence across unseen KIRA runs remains uncertain.
  - BigAI causal-mechanism claims remain bounded to behavioral reconstruction.
  - Timeout/stall attribution for BigAI is partially indirect in this lane because cluster counts come from `answered_questions.md` rather than opening each timeout task trajectory.
- preflight_likely_blind_spots:
  - Hidden controller policy that decides verifier presence/absence in BigAI runs.
  - Direct benchmark contract causal contribution for timeout-heavy failures.
  - Source-backed restart/resume implementation linkage for failure envelopes.
  - Full long-tail timeout run corpus beyond the cited cluster summary.
- preflight_blockers:
  - none
- coverage_used:
  - control surfaces:
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/brief.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/inputs/support_subagent_rules.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/brief.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
    - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/synthesis/principal_synthesis.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/synthesis/principal_synthesis.md`
    - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - required trajectory targets:
    - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
    - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
    - `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
    - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
    - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
    - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
    - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
    - `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`
    - `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`
    - `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
  - additional required-case-study pressure:
    - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
    - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
    - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
  - required local analysis:
    - `research/analysis/bigai_trace_layer/output/answered_questions.md`
  - support artifacts produced in this lane:
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/trajectory_support_failure_timeline.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/trajectory_support_terminal_failure_matrix.md`
- coverage_not_yet_used:
  - `research/sources/trajectories/BigAI/extract-moves-from-video/20be4239-23ea-49e2-afa1-c5098adeccf3.tar.gz`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/71ef0a56-0b53-4639-974a-0190139c059c.tar.gz`
  - `research/sources/trajectories/BigAI/db-wal-recovery/8586f6b0-3d1c-4eee-86b8-eee44cfad6c5.tar.gz`
  - `research/sources/trajectories/BigAI/db-wal-recovery/aea97873-3af7-4954-8c4f-a32b01b7cc99.tar.gz`
  - `research/sources/trajectories/BigAI/headless-terminal/955f47f3-f86f-4989-a975-1299ed63a173.tar.gz`
  - `research/sources/benchmarks/**`
  - `research/sources/codebases/**`
  - `research/sources/papers/**`
  - `research/sources/docs/**`
  - `research/sources/informal/**`
  - `research/sources/issues/**`
  - `research/sources/postmortems/**`
  - timeout-heavy BigAI trajectories cited by cluster but not directly opened in this pass (`torch-pipeline-parallelism`, `train-fasttext`, `caffe-cifar-10`, `qemu-startup`).
- evidence_classes_touched:
  - trajectories
  - relevant local analysis
  - wave control artifacts
- priority_sources_not_yet_read:
  - `research/sources/trajectories/BigAI/torch-pipeline-parallelism/**`
  - `research/sources/trajectories/BigAI/train-fasttext/**`
  - `research/sources/trajectories/BigAI/caffe-cifar-10/**`
  - `research/sources/trajectories/BigAI/qemu-startup/**`
  - `research/sources/benchmarks/**`
  - `research/sources/codebases/deepagents/**`
  - `research/sources/codebases/KIRA/**`
  - `research/sources/codebases/a-evolve/**`
  - `research/sources/informal/**`
  - `research/sources/issues/**`
  - `research/sources/postmortems/**`
- support_artifacts_used:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/trajectory_support_failure_timeline.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/trajectory_support_terminal_failure_matrix.md`
- support_artifacts_requested_or_deferred:
  - produced in-lane:
    - `trajectory_support_failure_timeline.md`
    - `trajectory_support_terminal_failure_matrix.md`
  - deferred:
    - timeout-task expanded run inventory for direct per-run attribution
    - benchmark-contract sidecar map pending potential fifth-lane activation
- coverage_register_updates_needed:
  - Update failure_taxonomy Wave 01 state from `packet prepared, not started` to `trajectory lane first-pass complete` with explicit evidence-strength caveats.
  - Keep carry-forward warning that BigAI claims remain behavioral reconstruction.
  - Keep explicit caveat that `extract-moves-from-video` remains thin and cannot carry high-confidence closure attribution.
  - Mark that required trajectory case studies were updated and missing `headless_terminal.md` was created.
- required_dossier_updates:
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/tool_use_and_gateways.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/verification_and_replay.md`
  - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/execution_control_and_terminal_failures.md`
- direct_behavior_observations:
  - claim_id: FT-W01-T1
    observation: DeepAgents `extract-moves-from-video` aborts almost immediately with `CancelledError`, leaving no usable completion or recovery evidence in the visible run.
    inference: This is an evidence-absence failure mode (coverage collapse), not a defensible family-level task-failure attribution.
    confidence: high
    weakness: none for the observation; attribution is explicitly bounded.
    evidence_paths:
      - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
  - claim_id: FT-W01-T2
    observation: DeepAgents `cancel-async-tasks` reports `max_running 2`, `cleaned [0, 1]`, and exception-path cleanup `cleaned ['fail', 'ok-1', 'ok-2']` after explicit verification pressure.
    inference: In this family, process lifecycle handling is defended by inline cancellation/cleanup checks rather than an external verifier actor.
    confidence: high
    weakness: queued-but-never-started task cleanup is not proven by this slice.
    evidence_paths:
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - claim_id: FT-W01-T3
    observation: DeepAgents `db-wal-recovery` verifies artifact and state consistency with `json_length 11`, `db_length 11`, `keys_ok True`, `match_db True`, while noting `main.db-wal` disappearance after checkpoint.
    inference: This is a bounded recovery-success pattern with explicit postcondition proof and explicit side-effect acknowledgment.
    confidence: high
    weakness: mapping to framework-level verifier internals is unresolved.
    evidence_paths:
      - `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
  - claim_id: FT-W01-T4
    observation: Terminus-KIRA `extract-moves-from-video` surfaces unresolved count conflict (`201` vs `230` vs `262`) with OCR interruption and still proceeds under completion pressure (`mark_task_complete`).
    inference: This is a false-success pressure pattern: terminal-visible progress and artifact presence outrun defended correctness closure.
    confidence: high
    weakness: one run slice; cannot claim absolute family prevalence.
    evidence_paths:
      - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
  - claim_id: FT-W01-T5
    observation: Terminus-KIRA `cancel-async-tasks` shows early pseudo-success (`Cleanups executed: 0`) then stronger failure (`BaseException ... CancelledError`) before eventual suite-level `PASS` outcomes.
    inference: Cancellation correctness is fragile under stronger scenarios; iterative retest is necessary to avoid premature completion claims.
    confidence: high
    weakness: none on the run-local observation.
    evidence_paths:
      - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - claim_id: FT-W01-T6
    observation: Terminus-KIRA `db-wal-recovery` loses target artifact grounding (`/app/main.db-wal` missing), enters overlay/host spelunking (`/var/lib/docker` probes, mount attempts, permission denial), and mutates `/app` structure (`mv /app /app.bak`, `mkdir /app`) without visible closure artifact.
    inference: This is terminal-grounding and repo-state control drift, not merely model weakness; environment exploration overtakes bounded recovery objective.
    confidence: medium
    weakness: full-run completeness is unknown; unseen continuation could alter end-state.
    evidence_paths:
      - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  - claim_id: FT-W01-T7
    observation: BigAI `extract-moves-from-video` shows high-frequency process lifecycle control (`wait_shell_command`/`kill_shell_command`) across long OCR/extraction loops with no visible terminal verifier closure in the inspected slice.
    inference: Execution-control machinery is active, but closure remains under-evidenced in this slice; process supervision alone does not imply completion truth.
    confidence: medium
    weakness: behavioral reconstruction only; slice completeness risk.
    evidence_paths:
      - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
  - claim_id: FT-W01-T8
    observation: BigAI `cancel-async-tasks` and `db-wal-recovery` repeatedly show verifier-mediated gating with explicit `verification_result_status` outcomes and delivery-directory cleanliness checks.
    inference: In this family, failure and recovery attribution must separate executor-side logic success from verifier/cleanup gate success.
    confidence: high
    weakness: mechanism internals remain unobserved (behavioral reconstruction).
    evidence_paths:
      - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
      - `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
      - `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`
      - `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
      - `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`
  - claim_id: FT-W01-T9
    observation: `answered_questions.md` reports timeout concentration on hard systems tasks (`torch-pipeline-parallelism`, `train-fasttext`, `caffe-cifar-10`, `qemu-startup`) and records verifier-presence asymmetry plus verifier-pass/overall-fail coexistence.
    inference: Timeout/stall and false-success families must remain distinct from one another and from pure model-failure narratives.
    confidence: medium
    weakness: this lane used summary-level local analysis rather than opening each timeout task trajectory.
    evidence_paths:
      - `research/analysis/bigai_trace_layer/output/answered_questions.md`
- workflow_patterns:
  - Pattern A: inline verification and closure in-run (DeepAgents) can defend process lifecycle and state recovery without a separate visible verifier role.
  - Pattern B: completion checklist pressure without contradiction closure (KIRA extract) creates false-success risk.
  - Pattern C: verifier-mediated closure (BigAI behavioral reconstruction) imposes dual gates: task logic correctness and delivery-state hygiene.
  - Pattern D: when primary artifact paths disappear (`main.db-wal`), recovery can degrade into environment archaeology and control drift.
- verification_and_recovery_patterns:
  - DeepAgents:
    - verification and recovery are tightly coupled to explicit postcondition checks.
    - strongest evidence is cancellation cleanup and DB-vs-artifact equality checks.
  - Terminus-KIRA:
    - recovery quality is scenario-sensitive; stronger tests can overturn earlier apparent success.
    - recovery can collapse into substrate probing when terminal grounding is lost.
  - BigAI (behavioral reconstruction):
    - planner/executor/verifier loops show clear fail-then-repair cycles.
    - verifier status is informative but not identical to final run success in corpus-level local analysis.
- failure_candidates:
  - candidate_id: FT-W01-FC1
    symptom: execution-control loss through early cancellation/truncation
    likely_causes: run interruption or infrastructure timeout/truncation pressure
    contribution_split: mixed (`environment` + `harness visibility`), not assignable to model quality alone
    confidence: high
    evidence_paths:
      - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
  - candidate_id: FT-W01-FC2
    symptom: terminal-grounding loss and repo-state/control drift in recovery task
    likely_causes: artifact-path loss, over-escalation into host/container substrate probing, weak recovery boundarying
    contribution_split: mixed (`harness behavior` + `environment constraints`)
    confidence: medium
    weakness: single visible KIRA run may not represent all KIRA attempts
    evidence_paths:
      - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  - candidate_id: FT-W01-FC3
    symptom: process lifecycle failure under cancellation pressure before hardening
    likely_causes: incomplete cancellation propagation/cleanup logic and underspecified early tests
    contribution_split: mostly `harness implementation`, with minor scenario-selection/test-design contribution
    confidence: high
    evidence_paths:
      - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
      - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
  - candidate_id: FT-W01-FC4
    symptom: timeout and stall pressure concentrated in hard systems tasks
    likely_causes: workload complexity, long-running shell operations, and verification/runtime budget limits
    contribution_split: mixed (`task/environment complexity` + `harness orchestration`)
    confidence: medium
    weakness: no direct per-run timeout trace opened in this lane
    evidence_paths:
      - `research/analysis/bigai_trace_layer/output/answered_questions.md`
  - candidate_id: FT-W01-FC5
    symptom: false-success risk from unresolved contradictions or verifier/overall-outcome mismatch
    likely_causes: insufficient contradiction closure before completion signaling; split acceptance layers
    contribution_split: mixed (`harness completion protocol` + `benchmark acceptance contract`)
    confidence: medium
    weakness: requires eval lane for stronger benchmark-blindness attribution.
    evidence_paths:
      - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
      - `research/analysis/bigai_trace_layer/output/answered_questions.md`
- cross_family_comparisons:
  - DeepAgents provides the strongest minimal-sufficient baseline for defended closure via direct artifact/state checks.
  - Terminus-KIRA shows strongest visible evidence for drift and contested completion in this wave's failure domain.
  - BigAI shows strongest visible process governance (planner/executor/verifier), but still exhibits timeout/finality ambiguity at corpus scale; this remains behavioral reconstruction.
  - Cross-family conclusion: execution-control and terminal failures form real families, but attribution is mixed and cannot be collapsed into one root-cause class.
- contradiction_notes:
  - Contradiction 1: stronger orchestration (BigAI role-separation) coexists with timeout-heavy failures and verifier-pass/overall-fail mismatch at corpus scale.
  - Contradiction 2: minimal inline proof (DeepAgents) can be stronger than richer role choreography when artifact checks are explicit.
  - Contradiction 3: KIRA completion-gate ritual does not guarantee contradiction closure in extraction or recovery grounding.
  - Contradiction 4: failure absence and evidence absence differ materially; `extract-moves` slices are under-saturated.
- confidence_notes:
  - High-confidence claims are run-local observations with direct terminal evidence.
  - Medium-confidence claims are cross-family prevalence/causal splits weakened by partial slices, behavioral reconstruction constraints, or summary-level timeout evidence.
  - No low-confidence claims were promoted in this output.
- open_questions:
  - Which timeout-heavy BigAI failures are mainly verifier-budget/contract failures versus executor lifecycle failures?
  - What specific KIRA control-surface changes prevent recovery drift once the primary artifact path disappears?
  - How often do verifier cleanliness gates prevent false success in practice across non-BigAI families?
  - Which headless-terminal failures are framework defects versus test harness artifacts?
- next_hand_off_target:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/contradiction_analyst.md`
