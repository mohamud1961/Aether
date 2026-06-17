# Failure Taxonomy Wave 01 Principal Synthesis

Status date: 2026-04-10

Wave

- overall Deep Synthesis core wave: Wave 07
- artifact-local wave: `failure_taxonomy` Wave 01
- wave: `wave_01_execution_control_and_terminal_failures`

Overall judgment

- Wave 01 materially opens `failure_taxonomy`.
- The strongest supported conclusion is that execution-control and terminal failures are real, recurring, and mixed-cause.
- The wave supports `pass_with_warnings`.
- The wave is now principal-complete and checklist-ready.
- It is not yet accepted at the wave level.
- It is not artifact completion.
- No failure family is `decision_ready`.
- BigAI remains `behavioral reconstruction`.

What this wave resolved

- Execution-control and terminal failures form real failure families rather than one generic "bad run" bucket.
  - Direct trajectory evidence supports cancellation cleanup problems, terminal-grounding drift, false-success pressure, and verifier/cleanup-gated recovery (`tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/trajectory_failure_analyst.md`).
  - Source evidence supports real implementation surfaces for interrupt/cancel/kill handling, process cleanup, verification boundaries, and local harness gaps (`tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_source_reconstruction_analyst.md`).
  - Literature and informal evidence support execution-control failure pressure as a harness/control-loop issue, while also warning against over-attribution (`tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/literature_papers_docs_analyst.md`, `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/informal_issues_postmortems_analyst.md`).
- Failure attribution should default to `mixed` unless stronger evidence isolates a single cause.
  - The current evidence repeatedly mixes model behavior, harness lifecycle control, environment constraints, and benchmark/verification blind spots.
  - This is not a model-only failure wave and not a harness-only failure wave.
- `headless_terminal.md` is no longer missing.
  - The case study exists at `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`.
  - Some first-pass lane outputs still refer to it as missing; that is stale state, not a current support-track blocker.
- Timeout/stall failure exists as a pressure cluster, but it is not yet strong enough as a direct per-run failure taxonomy.
  - The timeout-heavy BigAI evidence is still summary-routed through `research/analysis/bigai_trace_layer/output/answered_questions.md`.
  - It should remain `medium` confidence until direct timeout-heavy trajectories are opened.
- False-success pressure must split into subfamilies rather than one collapsed bucket:
  - verifier omission or weak verifier gate
  - benchmark or grader blindness
  - completion-checklist pressure without contradiction closure
  - verifier-pass versus overall-fail mismatch

What changed because of contradiction review

- I am not promoting timeout/stall as a fully consolidated failure family.
  - It is a real pressure cluster, but direct per-run attribution is still too thin.
- I am not treating DeepAgents `extract-moves-from-video` as an execution-control failure observation.
  - In this wave it is better treated as evidence absence / early abort pressure, not a strong failure-family datapoint.
- I am not promoting the literature lane's gateway-contract and permission-split claims as new Wave 01 failure families.
  - Those belong mainly to the inherited tools/environment/permissions mechanism surface from `mechanism_map` Wave 05.
  - They remain useful context only where they directly explain execution-control failure.
- I am not collapsing process-lifecycle failure under cancellation into a single primary cause.
  - The current synthesis preserves mixed contributions from harness implementation, scenario/test design, environment constraints, and model behavior.
- I am not treating benchmark-blindness as causally closed.
  - No eval/benchmark fifth lane ran, so benchmark-blindness remains a bounded warning rather than a promoted causal attribution.
- I am explicitly carrying forward the missing codebase support maps.
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_support_execution_failure_map.md` is missing.
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_support_interrupt_cancellation_map.md` is missing.
  - This does not block principal synthesis, but should be repaired or absorbed before later failure-taxonomy closure.

Failure cards

```text
FAILURE_CARD
- failure_id: terminal_grounding_and_repo_state_drift
- name: Terminal Grounding And Repo-State Drift
- short_definition: The agent loses reliable alignment with the actual terminal, working directory, artifact, or repo state, causing recovery to become environment archaeology rather than bounded task progress.
- visible_symptoms:
  - repeated exploration of filesystem or repo state
  - conflicting claims about what has been fixed
  - recovery loops after artifact disappearance or wrong-state assumptions
  - unresolved state contradictions despite apparent command progress
- severity: high
- recoverability: partially_recoverable
- likely_failure_class: mixed
- likely_stage: recovery
- direct_observations:
  - Terminus-KIRA `db-wal-recovery` shows recovery drift and contested completion under missing WAL/artifact pressure.
  - BigAI and DeepAgents recovery slices show that artifact paths and delivery-state hygiene can dominate final acceptance.
- inferred_root_causes:
  - weak workspace-state accounting
  - insufficient postcondition checks
  - brittle recovery after artifact loss
  - mixed environment and harness visibility failure
- evidence_paths:
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/trajectory_failure_analyst.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/trajectory_support_terminal_failure_matrix.md
  - tracking/collab/stage_02_synthesis/trajectory_case_studies/db_wal_recovery.md
- evidence_types:
  - trajectory
  - support_artifact
  - case_study
- affected_harness_areas:
  - execution
  - recovery
  - verification
  - workspace
- contradictory_or_complicating_evidence:
  - Some runs eventually recover, so this is not always terminal.
  - Attribution is mixed and cannot be assigned only to model behavior.
- downstream_effects:
  - false progress
  - late recovery loops
  - verifier or final-state mismatch
- candidate_mitigating_mechanisms:
  - explicit artifact continuity
  - cwd/workdir/path contract
  - cleanup-confirmed completion
  - postcondition proof before final answer
- likely_eval_implications:
  - evals should distinguish correct final artifact state from plausible but wrong-state terminal progress.
- confidence: high
- open_questions:
  - How often does this drift appear outside the required `db-wal-recovery` and workspace-heavy slices?
```

```text
FAILURE_CARD
- failure_id: cancellation_and_process_lifecycle_breakdown
- name: Cancellation And Process-Lifecycle Breakdown
- short_definition: The agent or harness cannot reliably stop, wait for, clean up, or verify long-running or asynchronous processes under cancellation pressure.
- visible_symptoms:
  - incomplete cleanup
  - stuck or runaway process state
  - inconsistent cancellation outcome
  - pass only after repair or strengthened cleanup checks
- severity: high
- recoverability: partially_recoverable
- likely_failure_class: mixed
- likely_stage: tool_use
- direct_observations:
  - DeepAgents `cancel-async-tasks` exposes cleanup and max-running checks.
  - Terminus-KIRA `cancel-async-tasks` exposes early pseudo-success and later stronger cancellation failure before eventual pass.
  - BigAI cancellation slices show verifier and delivery-directory cleanliness gates as behavioral reconstruction.
- inferred_root_causes:
  - weak process lifecycle control
  - insufficient cleanup postconditions
  - timeout/cancel semantics not coupled tightly enough to verification
  - task/scenario design can amplify the failure
- evidence_paths:
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/trajectory_failure_analyst.md
  - tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/synthesis/principal_synthesis.md
- evidence_types:
  - trajectory
  - case_study
  - mechanism_synthesis
- affected_harness_areas:
  - execution
  - recovery
  - verification
  - tools
- contradictory_or_complicating_evidence:
  - The exact contribution split between harness implementation, model action choice, and test/scenario design varies by run.
  - BigAI remains behavioral reconstruction only.
- downstream_effects:
  - false cleanup
  - late failure after apparent progress
  - verifier/final-state mismatch
- candidate_mitigating_mechanisms:
  - explicit wait/kill lifecycle tracking
  - cleanup-confirmed completion
  - bounded retries
  - process group cleanup checks
- likely_eval_implications:
  - cancellation evals should inspect process state and cleanup artifacts, not only final textual answer.
- confidence: high for the family; medium for primary-cause attribution
- open_questions:
  - Which cancellation failures are mostly implementation defects versus scenario or benchmark-design artifacts?
```

```text
FAILURE_CARD
- failure_id: false_success_from_weak_or_misaligned_acceptance
- name: False Success From Weak Or Misaligned Acceptance
- short_definition: A run appears complete or locally verified while unresolved contradictions, missing cleanup, or benchmark/grader blindness leave actual success uncertain.
- visible_symptoms:
  - verifier pass but overall failure
  - final response despite unresolved contradiction
  - plausible answer without terminal-level verifier closure
  - completion checklist pressure without full contradiction resolution
- severity: high
- recoverability: unclear
- likely_failure_class: mixed
- likely_stage: completion
- direct_observations:
  - KIRA `extract-moves-from-video` carries false-success pressure and unresolved count contradictions.
  - BigAI analysis preserves verifier-pass / overall-fail divergence.
  - Literature sources show benchmark contracts can check final state while ignoring important command-stream or process details.
- inferred_root_causes:
  - verifier omission or weak verifier gate
  - benchmark metric mismatch
  - completion pressure outrunning contradiction closure
  - final answer acceptance not coupled to the right artifact checks
- evidence_paths:
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/trajectory_failure_analyst.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/literature_papers_docs_analyst.md
  - tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md
  - research/sources/papers/papers_text/src_pap_f6aa42bfdc1a.txt
- evidence_types:
  - trajectory
  - paper
  - case_study
- affected_harness_areas:
  - verification
  - completion
  - eval
- contradictory_or_complicating_evidence:
  - No eval/benchmark fifth lane ran, so benchmark-blindness attribution is bounded.
  - Some false-success evidence is run-local rather than broad prevalence evidence.
- downstream_effects:
  - inflated success estimate
  - misleading handoff to eval design
  - hidden failure modes behind a pass/fail label
- candidate_mitigating_mechanisms:
  - layered verifier / grader / replay separation
  - artifact-backed postcondition proof
  - cleanup-confirmed completion
  - contradiction-aware finalization
- likely_eval_implications:
  - Future evals should separate verifier omission, benchmark-blindness, and final-answer contradiction pressure.
- confidence: medium
- open_questions:
  - Does verifier-pass / overall-fail divergence mainly reflect benchmark contract design, harness completion policy, or hidden task-specific grading behavior?
```

```text
FAILURE_CARD
- failure_id: timeout_and_stall_pressure
- name: Timeout And Stall Pressure
- short_definition: Long-running terminal work can stall, loop, or time out when lifecycle budgets, recovery loops, or environment constraints are not bounded well enough.
- visible_symptoms:
  - long-running non-progress
  - repeated retries without resolved state change
  - timeout concentration in hard systems tasks
  - stalled queue or non-responsive interruption
- severity: medium
- recoverability: unclear
- likely_failure_class: mixed
- likely_stage: multi_stage
- direct_observations:
  - Informal sources show recurring timeout, stall, and non-responsive interrupt pressure.
  - BigAI timeout-heavy clusters are visible in summary-level local analysis.
- inferred_root_causes:
  - weak watchdog and bounded-retry discipline
  - environment/infrastructure difficulty
  - possible model reasoning loops
  - benchmark budget pressure
- evidence_paths:
  - research/analysis/bigai_trace_layer/output/answered_questions.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/informal_issues_postmortems_analyst.md
  - tracking/collab/stage_02_synthesis/informal_cluster_dossiers/execution_control_and_terminal_failures.md
- evidence_types:
  - local_analysis
  - informal_source
- affected_harness_areas:
  - execution
  - recovery
  - orchestration
  - eval
- contradictory_or_complicating_evidence:
  - Timeout-heavy BigAI trajectories were not directly opened in this pass.
  - Cluster existence is stronger than causal attribution.
- downstream_effects:
  - wasted budget
  - incomplete state
  - hidden non-progress
- candidate_mitigating_mechanisms:
  - watchdogs
  - bounded retries
  - explicit interrupt propagation
  - progress checks
- likely_eval_implications:
  - Direct timeout-heavy trajectories should be sampled before promoting this beyond pressure-cluster status.
- confidence: medium
- open_questions:
  - Which timeout-heavy failures are primarily environment/infrastructure failures versus harness lifecycle failures?
```

What still requires another wave

- Direct timeout-heavy BigAI trajectories need to be opened before timeout/stall becomes a strong per-run failure family.
- False-success needs eval/benchmark-side pressure if we want stronger causal attribution around benchmark-blindness.
- The missing codebase support maps should be produced or explicitly retired before artifact closure.
- A-Evolve remains source-strong but trajectory-thin in this failure wave.

Local harness implications

- The local harness needs concrete runtime implementations for execution, verification, and recovery before these failure families can be experimentally stress-tested.
- `VerificationBlock` should not only check final answer text; it should inspect process state, cleanup state, and artifact postconditions when relevant.
- `RecoveryBlock` should represent interrupt/cancel/timeout outcomes explicitly rather than treating them as generic tool errors.
- `ExecutionBlock` variants should expose enough lifecycle state to distinguish:
  - process still running
  - killed
  - timed out
  - cleaned up
  - verified
  - unverifiable

Coverage not yet used

- direct BigAI timeout-heavy trajectories:
  - `research/sources/trajectories/BigAI/torch-pipeline-parallelism/**`
  - `research/sources/trajectories/BigAI/train-fasttext/**`
  - `research/sources/trajectories/BigAI/caffe-cifar-10/**`
  - `research/sources/trajectories/BigAI/qemu-startup/**`
- direct benchmark implementations and grader/replay contracts under `research/sources/benchmarks/**`
- full local harness implementation audit beyond the current scaffold-level read
- direct A-Evolve trajectory reconciliation for Wave 01 failure families

Priority sources not yet read

- `research/sources/benchmarks/**`
- `research/sources/trajectories/BigAI/torch-pipeline-parallelism/**`
- `research/sources/trajectories/BigAI/train-fasttext/**`
- `research/sources/trajectories/BigAI/caffe-cifar-10/**`
- `research/sources/trajectories/BigAI/qemu-startup/**`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_support_execution_failure_map.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_support_interrupt_cancellation_map.md`

Support track updates

- Required case-study state:
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md` exists
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md` exists
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/db_wal_recovery.md` exists
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md` exists
- Required informal cluster state:
  - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/execution_control_and_terminal_failures.md` exists
- Missing wave-local support maps:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_support_execution_failure_map.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_support_interrupt_cancellation_map.md`

Next governed step

- Run Failure Taxonomy Wave 01 checklist adjudication.
