CODEBASE_SOURCE_RECON_OUTPUT
- artifact: failure_taxonomy / wave_01_execution_control_and_terminal_failures
- role: codebase/source-reconstruction analyst
- preflight_scope_confirmed:
  - confirmed this lane is a vertical failure-domain pass on execution-loop breakdown, interrupt/cancel/kill failures, timeout and cleanup failure, verifier omission/false-success surfaces, and repo-state/control drift.
  - confirmed this lane is implementation-anchor first (mirrored source and local harness code), with trajectories used to test whether source-visible control mechanisms hold under failure pressure.
  - confirmed optional eval/benchmark fifth lane remains inactive for this lane because current attribution can be made from source + trajectory evidence without benchmark-contract internals.
  - minimal-sufficient baseline kept explicit: terminal-first loops can still fail; richer orchestration does not automatically remove execution-control failures.

- preflight_planned_read_order:
  - wave control surfaces and carry-forward cautions.
  - mirrored source families (`deepagents`, `KIRA`, `a-evolve`, `quarantine/claw-code`) plus local harness (`blocks/`, `runner/`, `evals/`).
  - failure-heavy trajectory slices (`extract-moves-from-video`, `cancel-async-tasks`, `db-wal-recovery`, `headless-terminal`).
  - no-source BigAI trajectories as `behavioral reconstruction` only.
  - required support-track artifacts (dossiers, case studies, coverage register).

- preflight_critical_sources_selected:
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
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/synthesis/principal_synthesis.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/synthesis/principal_synthesis.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/synthesis/principal_synthesis.md`
  - source families:
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/local_shell.py`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/sandbox.py`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/async_subagents.py`
    - `research/sources/codebases/deepagents/libs/cli/deepagents_cli/agent.py`
    - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_manager.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_tools.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/session_manager.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/engine.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/scheduler_runtime.py`
    - `research/sources/codebases/a-evolve/agent_evolve/engine/loop.py`
    - `research/sources/codebases/a-evolve/agent_evolve/engine/versioning.py`
    - `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/react_solver.py`
    - `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/agent.py`
    - `research/sources/codebases/a-evolve/agent_evolve/benchmarks/tb2/terminal2.py`
    - `research/sources/codebases/quarantine/claw-code/**`
    - `blocks/**`
    - `runner/**`
    - `evals/**`
  - trajectory pressure:
    - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
    - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
    - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
    - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
    - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
    - `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
    - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
    - `research/sources/trajectories/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53-traj.txt`
    - `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`
    - `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
    - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
    - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
    - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`

- preflight_coverage_risks:
  - BigAI remains no-source and must stay `behavioral reconstruction`.
  - local harness execution/recovery/verifier surfaces are mostly interface docstrings, limiting direct local implementation attribution.
  - `quarantine/claw-code` is archive pressure with limited runtime traceability.
  - trajectory quality is uneven (`extract-moves-from-video` and parts of `headless-terminal` contain truncation/partial visibility).

- preflight_likely_blind_spots:
  - deepagents task-family-specific verifier implementation path for `db-wal-recovery` remains untraced in mirrored source.
  - KIRA cross-surface behavior between TerminusKira and KiraClaw scheduler/lanes remains only partially reconciled per task family.
  - BigAI controller policy for verifier optionality cannot be source-validated.
  - long-tail timeout clusters outside required slices were not expanded in this lane pass.

- preflight_blockers:
  - none

- coverage_used:
  - control surfaces listed in `preflight_critical_sources_selected`.
  - mirrored source and local harness surfaces listed in `preflight_critical_sources_selected`.
  - required trajectory slices listed in `preflight_critical_sources_selected`.
  - support-track artifacts read/updated context:
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/tool_use_and_gateways.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/verification_and_replay.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/db_wal_recovery.md`

- coverage_not_yet_used:
  - `research/sources/papers/**`
  - `research/sources/docs/**`
  - `research/sources/informal/**`
  - `research/sources/issues/**`
  - `research/sources/postmortems/**`
  - additional deepagents and KIRA long-tail task families beyond required Wave 01 slices.

- evidence_classes_touched:
  - mirrored codebases
  - trajectories
  - relevant local harness code
  - relevant local analysis/synthesis artifacts

- priority_sources_not_yet_read:
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/hitl.py`
  - `research/sources/codebases/deepagents/libs/cli/deepagents_cli/non_interactive.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/api.py`
  - `research/sources/codebases/a-evolve/agent_evolve/engine/trial.py`
  - timeout-heavy BigAI run clusters enumerated in `research/analysis/bigai_trace_layer/output/answered_questions.md`.

- support_artifacts_used:
  - none in this pass

- support_artifacts_requested_or_deferred:
  - deferred:
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_support_execution_failure_map.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_support_interrupt_cancellation_map.md`

- coverage_register_updates_needed:
  - update `tracking/collab/stage_02_synthesis/coverage_register/current_status.md` to mark Failure Taxonomy Wave 01 as in-progress with codebase lane first-pass output complete.
  - remove/resolve missing `headless_terminal.md` warning once case study is added.
  - keep carry-forward cautions explicit:
    - BigAI remains `behavioral reconstruction`
    - restart/resumability evidence is still uneven behaviorally
    - DeepAgents inline verifier attribution gap in `db-wal-recovery` remains open

- required_dossier_updates:
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/tool_use_and_gateways.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/verification_and_replay.md`
  - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/execution_control_and_terminal_failures.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/db_wal_recovery.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`

- source_backed_mechanisms:
  - claim_id: FT-W01-CB-01
    confidence: high
    observation: DeepAgents local execution backend explicitly runs shell commands with `shell=True`, no isolation, and timeout-to-exit-code-`124` behavior.
    inference: execution-loop breakdown risk includes direct host-shell coupling and timeout handling surfaces that can look like command failure but are actually control-budget failure.
    evidence_paths:
      - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/local_shell.py`

  - claim_id: FT-W01-CB-02
    confidence: high
    observation: DeepAgents async subagent lifecycle persists task IDs/states (`start`, `check`, `update`, `cancel`, `list`) inside runtime state.
    inference: interrupt/cancel correctness depends on lifecycle-state reconciliation, not just sending cancellation signals.
    evidence_paths:
      - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/async_subagents.py`

  - claim_id: FT-W01-CB-03
    confidence: high
    observation: TerminusKira enforces marker-based polling, block-timeout wrappers, and two-step completion confirmation (`task_complete` then confirmation pass).
    inference: KIRA source embeds explicit anti-false-success guardrails, but these guardrails are protocol-level and can still be undermined by weak verification evidence.
    evidence_paths:
      - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`

  - claim_id: FT-W01-CB-04
    confidence: high
    observation: KiraClaw process manager tracks background process state and escalates kill from SIGTERM to SIGKILL when needed; process tools expose list/poll/log/kill.
    inference: interrupt/kill failures are treated as first-class runtime concerns in KIRA-family source rather than ad hoc shell behavior.
    evidence_paths:
      - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_manager.py`
      - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_tools.py`

  - claim_id: FT-W01-CB-05
    confidence: medium
    observation: KiraClaw session lanes and scheduler runtime separate queued/running/completed/failed run state from schedule-driven run creation.
    inference: repo-state/control drift can originate in orchestration layer boundaries (scheduler -> lane -> engine) even when command execution itself is correct.
    weakens_confidence: this pass did not perform full end-to-end runtime replay across scheduler-produced runs.
    evidence_paths:
      - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/session_manager.py`
      - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/scheduler_runtime.py`
      - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/engine.py`

  - claim_id: FT-W01-CB-06
    confidence: high
    observation: A-Evolve has explicit loop control (`EvolutionLoop`) plus git-based version control/rollback that preserves rejected states in history.
    inference: repo-state drift is directly modeled as a controllable mechanism in a-evolve, not left to implicit shell discipline.
    evidence_paths:
      - `research/sources/codebases/a-evolve/agent_evolve/engine/loop.py`
      - `research/sources/codebases/a-evolve/agent_evolve/engine/versioning.py`

  - claim_id: FT-W01-CB-07
    confidence: high
    observation: A-Evolve terminal agent separates solve from verifier execution (`test.sh` with retry/timeout) and TB2 evaluation reads trajectory pass/fail outputs.
    inference: verifier omission and false-success surfaces are explicitly separated from executor behavior in source, enabling clearer failure attribution.
    evidence_paths:
      - `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/agent.py`
      - `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/react_solver.py`
      - `research/sources/codebases/a-evolve/agent_evolve/benchmarks/tb2/terminal2.py`

  - claim_id: FT-W01-CB-08
    confidence: high
    observation: local harness `blocks/`, `runner/`, and `evals/` are primarily interface/scaffold docstrings without concrete execution-loop, verifier, or recovery implementations.
    inference: current local harness has a structural omission risk: failure families can be named but not yet experimentally constrained by implemented control primitives.
    evidence_paths:
      - `blocks/execution/flat_loop.py`
      - `blocks/execution/guided_loop.py`
      - `blocks/execution/dag_loop.py`
      - `blocks/verification/double_confirm.py`
      - `blocks/recovery/remediation_inject.py`
      - `runner/agent.py`
      - `runner/evaluator.py`
      - `runner/docker_sandbox.py`
      - `evals/verification_eval.py`

- behavioral_reconstructions:
  - claim_id: FT-W01-CB-BR-01
    confidence: high
    observation: BigAI headless, cancellation, and WAL slices show planner/executor/verifier staging and explicit verifier closures (`verification_result_status: "PASSED"`) in successful runs.
    inference: BigAI behavior suggests layered execution-control doctrine with verifier-mediated closeout and cleanup pressure.
    evidence_paths:
      - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
      - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
      - `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`
    label: behavioral reconstruction

  - claim_id: FT-W01-CB-BR-02
    confidence: medium
    observation: BigAI runs show completion can be blocked by delivery-directory hygiene even after logic tests pass.
    inference: false-success avoidance in BigAI appears to include workspace cleanliness as a completion gate, not only functional test outcomes.
    weakens_confidence: no source-backed verifier policy for this criterion is available.
    evidence_paths:
      - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
    label: behavioral reconstruction

- subsystem_findings:
  - execution-loop breakdown:
    - DeepAgents local shell path exposes direct shell coupling and timeout hard-stops (`local_shell.py`).
    - KIRA adds marker polling and block timeout wrappers to bound command wait behavior (`terminus_kira.py`).
  - interrupt/cancel/kill failure:
    - KIRA has explicit background process lifecycle controls with kill escalation and process tooling (`process_manager.py`, `process_tools.py`).
    - DeepAgents async subagent state model treats cancellation as state transition, not only signal dispatch (`async_subagents.py`).
  - timeout and cleanup failure:
    - KIRA and BigAI trajectories both show cleanup as a first-class completion criterion; source in KIRA supports process cleanup controls, while BigAI remains behavioral.
    - DeepAgents headless trajectory shows timeout/teardown fragility (daemon-thread shutdown failure) followed by repair and successful re-verification.
  - verifier omission and false-success surfaces:
    - A-Evolve source cleanly separates executor and verifier surfaces (`terminal/agent.py`, `tb2/terminal2.py`).
    - KIRA double-confirm gate reduces but does not eliminate false-success pressure when evidence remains contradictory in trajectory slices.
  - repo-state/control drift:
    - a-evolve versioning/rollback is explicit source-backed drift control.
    - KIRA scheduler/lane split implies additional drift surfaces at orchestration boundaries.
    - local harness lacks implemented drift controls beyond interface declarations.

- source_behavior_matches:
  - KIRA source-level completion guardrails align with visible repeated completion-check pressure in trajectories.
    - source: `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - behavior: `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - KIRA process lifecycle tooling aligns with interruption/cleanup-heavy cancellation behavior demands.
    - source: `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_manager.py`
    - behavior: `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - DeepAgents guidance to verify-before-finish aligns with trajectory-visible verification prompts and post-fix rechecks in headless-terminal.
    - source: `research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py`
    - behavior: `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`

- source_behavior_mismatches:
  - DeepAgents `db-wal-recovery` trajectory has strong inline proof, but mirrored framework source path for that exact task verifier logic remains untraced.
    - source side: `research/sources/codebases/deepagents/libs/deepagents/deepagents/graph.py`
    - behavior side: `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
  - KIRA source has strong completion/verification protocol semantics, yet `extract-moves-from-video` and `headless-terminal` runs still show prolonged contradiction resolution and cleanup artifacts before final closure.
    - source side: `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - behavior side: `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`, `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
  - local harness contracts suggest swappable execution/verification/recovery blocks, but current files are not implemented runtime surfaces yet.
    - source side: `blocks/**`, `runner/**`, `evals/**`

- archive_or_visibility_limits:
  - `research/sources/codebases/quarantine/claw-code/` remains archive/snapshot pressure rather than a first-class mirrored runnable family in this lane.
  - BigAI remains strictly behavioral due to missing mirrored source codebase.
  - trajectory truncation in multimodal families weakens closure attribution for some runs.

- confidence_notes:
  - high confidence: source-backed claims for deepagents/KIRA/a-evolve execution-control mechanisms.
  - medium confidence: cross-family prevalence statements where trajectories are uneven or truncated.
  - medium confidence: KIRA scheduler-layer drift attribution absent full schedule-replay inspection.
  - low confidence: any claim requiring BigAI implementation internals (not available).

- open_questions:
  - where in deepagents mirrored source does task-family-specific inline postcondition verification (as seen in `db-wal-recovery`) get instantiated, if at all?
  - are KIRA scheduler-produced runs materially more prone to repo-state/control drift than direct terminal-run paths?
  - should Wave 01 activate eval lane to disambiguate verifier omission from benchmark-grader blindness in ambiguous false-success slices?
  - what minimum local harness implementation is needed before Wave 01 failure families can be experimentally stress-tested rather than only source/trajectory synthesized?

- next_hand_off_target:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/contradiction_analyst.md`
