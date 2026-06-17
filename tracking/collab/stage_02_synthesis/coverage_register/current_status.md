# Deep Synthesis Coverage Register

Status date: 2026-04-10

## Core-wave status

- `mechanism_map`
  - Wave 01 `exploratory_anchor`: complete
  - Wave 02 `execution_control_and_terminal_grounding`: accepted with carry-forward warnings
  - Wave 03 `verification_completion_and_recovery`: accepted with carry-forward warnings
    - strong core findings:
      - multi-family completion and verification structure is real
      - artifact-backed postcondition proof is a real family
      - cleanup-confirmed completion is real
      - verifier / grader / replay separation is real
    - active warnings:
      - BigAI remains `behavioral reconstruction`
      - restart/resumability remains under-evidenced behaviorally
      - DeepAgents task-level proof in `db-wal-recovery` is currently best explained as inline agent-authored verification rather than clearly mirrored framework verifier code
      - direct BigAI verifier-heavy pressure remains thin without `research/sources/trajectories/BigAI/adaptive-rejection-sampler/**`
      - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` remains empty, so direct path accounting still outranks organizer routing
  - Wave 04 `context_state_memory_workspace`: accepted with carry-forward warnings
    - strong core findings:
      - explicit artifact continuity and workspace state are the strongest current behavioral baseline
      - context compaction, session history, durable persistence, and workspace artifacts are distinct mechanism surfaces
      - workspace and branch hygiene are real but currently strongest in `git-multibranch` and path/session corruption regimes
      - runtime allocator-memory failures are distinct from coding-agent memory mechanisms
    - active warnings:
      - BigAI remains `behavioral reconstruction`
      - restart/resumability remains under-evidenced behaviorally
      - A-Evolve Wave 04 workspace findings are source-backed, not trajectory-backed
      - richer source-visible memory capacity in DeepAgents and KIRA exceeds what the required Wave 04 trajectories visibly exercise
      - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` remains empty, so direct path accounting still outranks organizer routing
  - Wave 05 `tools_environment_permissions`: accepted with carry-forward warnings
    - strong core findings:
      - tool gateway design is a real cross-family mechanism axis
      - cwd/workdir/path discipline is a first-order mechanism family
      - permission policy and execution capability boundaries are distinct layers
      - terminal-first minimal tooling remains the strongest direct Wave 05 baseline
      - process lifecycle and cancellation control are real tools-domain mechanism surfaces
    - active warnings:
      - BigAI remains `behavioral reconstruction`
      - robust permission safety remains under-evidenced at trajectory level
      - environment discovery remains `exploratory`
      - A-Evolve Wave 05 findings are source-backed, not trajectory-backed
      - `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md` was a Wave 05 support-track warning and has since been repaired
      - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` remains empty, so direct path accounting still outranks organizer routing
  - Wave 06 `planning_orchestration_and_interactions`: accepted with carry-forward warnings
    - strong core findings:
      - planning/replanning and delegation are real mechanism surfaces, not generic workflow narration
      - planner-first orchestration with conditional verifier gate is real in the required BigAI slices
      - source-backed delegation and role-boundary governance are real in deepagents, KIRA, and a-evolve
      - terminal-first single-agent baseline remains a live comparator against prestige orchestration claims
      - interaction contract fragility is a real cross-lane pressure surface
    - active warnings:
      - BigAI remains `behavioral reconstruction`
      - explicit role-separated orchestration is strongest in BigAI behavioral evidence and is not yet a proven cross-family universal family
      - deepagents and a-evolve source-visible delegation capacity exceeds required-task trajectory exercise
      - verifier optionality is visible but causally unresolved
      - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` remains empty, so direct path accounting still outranks organizer routing

- `failure_taxonomy`
  - Wave 01 `execution_control_and_terminal_failures`: accepted with carry-forward warnings
    - strong core findings:
      - execution-control and terminal failures are real recurring failure families
      - failure attribution is mixed and cannot be collapsed to model-only or harness-only
      - terminal-grounding and repo-state drift is a real failure family
      - cancellation and process-lifecycle breakdown is a real failure family
      - false-success pressure is real but requires subfamily separation
    - active warnings:
      - BigAI remains `behavioral reconstruction`
      - timeout/stall evidence is still summary-routed rather than direct per-run attribution
      - false-success benchmark-blindness is bounded because no eval/benchmark fifth lane ran
      - codebase support maps for execution failure and interrupt/cancellation were not produced
      - no failure family is `decision_ready`
  - Wave 02 `verification_completion_and_recovery_failures`: accepted with carry-forward warnings
    - eval fifth lane:
      - activated because verifier, grader, replay, recovery, and benchmark-contract logic are central
    - lane and gate status:
      - trajectory lane first-pass output exists
      - codebase/source lane first-pass output exists
      - literature lane first-pass output exists
      - informal lane first-pass output and follow-up output exist
      - eval/benchmark lane first-pass output exists
      - GPT contradiction output exists and returned `pass_with_warnings`
      - Claude contradiction output exists and returned `pass_with_warnings`
      - Gemini contradiction output does not exist on disk for this wave
      - principal synthesis exists
      - checklist adjudication exists and returned `pass_with_warnings`
    - principal findings:
      - verifier or completion success signals can diverge from final benchmark acceptance
      - inline checks, verifier artifacts, replay/state graders, LLM judges, cleanup checks, and final reward are distinct attribution layers
      - recovery/resume failure includes state/index drift, non-terminal recovery limbo, and environment-state invalidation pressure
      - benchmark-contract blindness is real pressure but bounded without deeper grader implementation reads
      - concrete mismatch cases visible in required runs:
        - BigAI `cancel-async-tasks` `98b7...`: in-run verifier pass narrative with bundle-level failed test/reward `0`
        - deepagents `cancel-async-tasks` `ca5a...`: local verification success narrative with bundle-level failed test/reward `0`
        - KIRA `extract-moves-from-video` `3df8...`: completion-pressure trajectory with bundle-level similarity failure/reward `0`
        - KIRA `db-wal-recovery` `3481...`: reward `0` with verifier output showing cwd/path invalidation pressure
    - active warnings:
      - BigAI remains `behavioral reconstruction`
      - Wave 01 codebase support-map debt remains open unless explicitly repaired or retired
      - no Wave 02 failure family is decision-ready before checklist adjudication
      - benchmark-contract blindness remains partly contract-level because several benchmark sources are README/snapshot captures rather than grader implementation reads
      - cleanup-confirmed invalid completion is only a subflag under false-completion/final-acceptance mismatch, not a separate family
      - BigAI extraction verifier omission remains provisional because it may be a trace-format artifact
      - A-Evolve Wave 02 behavior remains source-backed, not trajectory-backed
  - Wave 03 `context_state_memory_workspace_failures`: accepted with carry-forward warnings
    - eval fifth lane:
      - inactive by default
      - reactivation condition: benchmark state contracts, replay state, grader workspace expectations, or task persistence contracts become load-bearing
    - evidence shape:
      - four main lanes completed: trajectory, codebase/source reconstruction, literature/papers/docs, informal/issues/postmortems
      - contradiction outputs present from GPT, Claude, and Gemini
    - principal findings:
      - workspace/repo/branch/path drift is the strongest direct Wave 03 failure family
      - stale or misleading state is a real failure surface distinct from raw context-window pressure
      - compaction/summarization is an explicit state-operator failure surface, but direct required-trajectory evidence is still thinner than source/formal/informal support
      - session persistence and state handoff failures are real, but direct trajectory support is still thinner than source and issue support
      - runtime allocator-memory failures remain distinct from coding-agent context/state failures
    - active warnings:
      - BigAI remains `behavioral reconstruction`
      - Mechanism Map Wave 04 A-Evolve workspace findings are source-backed, not trajectory-backed
      - Wave 02 recovery/resume state fragility may overlap with Wave 03 state/persistence failures and must be reconciled rather than duplicated
      - post-compaction instruction loss is currently `single-lane, informal-only`
      - deferred Wave 03 support artifacts remain open debt:
        - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/trajectory_support_context_workspace_failure_matrix.md`
        - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/trajectory_support_memory_state_drift_cases.md`
        - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/literature_support_context_memory_failure_cluster.md`
        - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/informal_support_context_workspace_failure_cluster.md`
      - no Wave 03 failure family is decision-ready
  - Wave 04 `tools_environment_coordination_and_long_horizon_failures`: packet-prepared, not started
    - eval fifth lane:
      - inactive by default
      - reactivation condition: benchmark time budgets, grader/tool contracts, replay requirements, or benchmark workspace assumptions become load-bearing
    - planned core focus:
      - tool gateway and substrate mismatch
      - cwd/workdir/path contract failure
      - permission-policy versus runtime-capability mismatch
      - process lifecycle and cancellation breakdown
      - delegation, role-handoff, and replanning failure
      - timeout-heavy long-horizon coordination degradation
    - active warnings:
      - BigAI remains `behavioral reconstruction`
      - Mechanism Map Wave 05 permission safety remains under-evidenced behaviorally
      - Mechanism Map Wave 06 role-separated orchestration remains source-strong and BigAI-behavior-rich, not universally trajectory-proven
      - Wave 03 support-artifact debt remains open and should not be forgotten while Wave 04 runs
      - no Wave 04 failure family is decision-ready before lane execution, contradiction review, principal synthesis, and checklist adjudication

- `eval_implications`
  - not started

- `variant_family_seeds`
  - not started

## Support-track status

- `coverage_access`
  - `Gate A baseline_access_ready`: in progress
  - notes:
    - formal paper text access is materially complete
    - broader route-map closure is still incomplete

- `source_system_dossiers`
  - in progress
  - Wave 03 required dossiers now exist:
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
  - Wave 04 required dossier now exists:
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`

- `trajectory_case_studies`
  - required
  - Wave 03 required case studies now exist:
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/db_wal_recovery.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md`
  - Wave 04 required case studies now exist:
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/git_multibranch.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/break_filter_js_from_html.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/custom_memory_heap_crash.md`
  - Wave 05 required case studies are now repaired:
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`
    - existing carry-forward support still in use:
      - `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md`
      - `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`
  - Wave 06 required case studies now exist:
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/prove_plus_comm.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/cobol_modernization.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/openssl_selfsigned_cert.md`
  - Failure Taxonomy Wave 01 required case studies now exist:
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/db_wal_recovery.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`
  - Failure Taxonomy Wave 02 required case studies are in progress:
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/db_wal_recovery.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`
  - Failure Taxonomy Wave 03 required case studies are planned:
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/git_multibranch.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/break_filter_js_from_html.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/custom_memory_heap_crash.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/db_wal_recovery.md`

- `literature_dossiers`
  - structure exists
  - dossier depth still partial
  - Wave 03 required theme files now exist:
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/verification_and_replay.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/checkpoint_restore_and_resumability.md`
  - Wave 04 required theme files now exist:
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/context_and_memory.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/workspace_and_artifact_discipline.md`
  - Wave 05 required theme files now exist:
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/tool_use_and_gateways.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md`
  - Wave 06 required theme files now exist:
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/planning_and_replanning.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/delegation_and_role_separation.md`
  - Failure Taxonomy Wave 02 required theme files are in-progress updates:
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/verification_and_replay.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/checkpoint_restore_and_resumability.md`
  - Failure Taxonomy Wave 03 required theme files are planned updates:
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/context_and_memory.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/workspace_and_artifact_discipline.md`

- `informal_cluster_dossiers`
  - structure exists
  - Wave 03 dossier exists:
    - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/verification_completion_and_recovery.md`
  - Wave 04 dossier exists:
    - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/context_state_memory_workspace.md`
  - Wave 05 dossier exists:
    - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/tools_environment_permissions.md`
  - Wave 06 dossier exists:
    - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/planning_orchestration_and_interactions.md`
  - Failure Taxonomy Wave 01 dossier exists:
    - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/execution_control_and_terminal_failures.md`
  - Failure Taxonomy Wave 02 dossier now has lane first-pass content:
    - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/verification_completion_recovery_failures.md`
  - Failure Taxonomy Wave 03 dossier stub now exists:
    - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/context_state_memory_workspace_failures.md`

- `eval_benchmark_dossiers`
  - structure exists
  - Wave 03 dossier exists:
    - `tracking/collab/stage_02_synthesis/eval_benchmark_dossiers/verification_completion_and_recovery.md`
  - Failure Taxonomy Wave 02 eval dossier updates are in progress:
    - `tracking/collab/stage_02_synthesis/eval_benchmark_dossiers/verification_completion_and_recovery.md`
    - `tracking/collab/stage_02_synthesis/eval_benchmark_dossiers/verification_completion_recovery_failures.md`

## Paper-text status

- source:
  - `research/sources/papers/papers_text/review_summary.md`
- totals:
  - `200` readable
  - `194` clean
  - `6` usable_with_caveats
  - `0` ocr_needed
  - `0` failed

## First dossier set

- `KIRA`: required, not yet complete as a standalone dossier
- `deepagents`: required, not yet complete as a standalone dossier
- `a-evolve`: required, not yet complete as a standalone dossier
- `claw-code`: required, not yet complete as a standalone dossier
- `BigAI behavioral dossier`: required, not yet complete as a standalone dossier
- `autoagent`: second-tier, useful when relevant

## Carry-forward warnings from accepted work

- BigAI remains `behavioral reconstruction`, not source-backed implementation
- repo-state-safe cleanup is still less saturated than terminal control/cancellation
- archive-only `src_cod_*` pressure remains exploratory
- internal-verifier versus external-grader mismatch is established but not fully causally explained
- formal and eval long-tail depth remains incomplete
- `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` remains empty, so direct path accounting still outranks organizer routing
- explicit role-separated orchestration remains under-saturated behaviorally outside BigAI-heavy evidence

## Wave 03 carry-forward warnings

- do not promote restart/resumability beyond `exploratory`
- do not collapse inline proof, external grader, replay gate, and final run acceptance into one completion layer
- do not treat DeepAgents inline proof in `db-wal-recovery` as mirrored framework verifier code until traced more directly
- keep BigAI explicitly at `behavioral reconstruction`
- keep the remaining evidence limits visible even though Wave 03 is accepted at the wave level

## Failure Taxonomy Wave 04 trajectory lane status (2026-04-11)

- `failure_taxonomy` Wave 04 `tools_environment_coordination_and_long_horizon_failures`
  - trajectory lane first-pass output now exists:
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/trajectory_failure_analyst.md`
  - trajectory support artifacts now exist:
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/trajectory_support_tool_coordination_failure_matrix.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/trajectory_support_long_horizon_failure_timeline.md`
  - trajectory-lane carry-forward warnings:
    - BigAI remains `behavioral reconstruction`.
    - timeout-heavy attribution is strong behaviorally but still partially summary-routed via `answered_questions.md` for concentration claims.
    - required tar payload internals are not yet fully reopened for all required slices.
    - mixed-cause boundaries (tool contract vs policy/runtime vs long-horizon budget pressure) remain active contradiction-review risk.
