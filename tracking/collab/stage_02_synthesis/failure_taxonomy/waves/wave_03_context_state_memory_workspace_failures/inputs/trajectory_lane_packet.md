# Failure Taxonomy Wave 03 Trajectory Lane Packet

Use this packet for the Wave 03 `trajectory/failure analyst`.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_trajectory_failure_analyst_prompt.md`
3. this file

## Exact role

- `trajectory/failure analyst`

## Exact objective for Wave 03

Produce behavior-anchored failure attribution for `context_state_memory_workspace_failures`.

You must synthesize failures in:

- context loss or compaction failure
- stale/misleading memory state
- workspace/repo/branch/path drift
- session persistence and state handoff failure
- runtime memory pressure, kept distinct from coding-agent context/memory failure

This is a failure-taxonomy wave, not a generic context/memory recap.

## Exact files to read first

1. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/brief.md`
2. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/support_subagent_rules.md`
3. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/README.md`
4. `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
5. `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
6. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
7. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_PHASE_AND_WAVE_OPERATING_PLAN.md`
8. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
9. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/adjudication/checklist_adjudicator.md`
10. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`

Then read required trajectory targets:

- `research/sources/trajectories/BigAI/git-multibranch/`
- `research/sources/trajectories/deepagents/git-multibranch/`
- `research/sources/trajectories/terminus-kira/git-multibranch/`
- `research/sources/trajectories/BigAI/break-filter-js-from-html/`
- `research/sources/trajectories/deepagents/break-filter-js-from-html/`
- `research/sources/trajectories/terminus-kira/break-filter-js-from-html/`
- `research/sources/trajectories/BigAI/custom-memory-heap-crash/`
- `research/sources/trajectories/deepagents/custom-memory-heap-crash/`
- `research/sources/trajectories/terminus-kira/custom-memory-heap-crash/`
- `research/analysis/bigai_trace_layer/output/answered_questions.md`

## Exact required dossier updates

- `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/context_and_memory.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/workspace_and_artifact_discipline.md`
- `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/context_state_memory_workspace_failures.md`

## Exact required case-study updates

- `tracking/collab/stage_02_synthesis/trajectory_case_studies/git_multibranch.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/break_filter_js_from_html.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/custom_memory_heap_crash.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/db_wal_recovery.md`

## Exact output path

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/trajectory_failure_analyst.md`

Follow-up outputs must use:

- `.../trajectory_failure_analyst__followup_01.md`
- `.../trajectory_failure_analyst__followup_02.md`
- `.../trajectory_failure_analyst__revision_01.md`

## Exact support artifacts this lane may request

- `trajectory_support_context_workspace_failure_matrix.md`
- `trajectory_support_memory_state_drift_cases.md`

## Exact stop conditions

Stop and hand back if trajectory coverage is too thin for honest attribution, or if mixed-cause separation cannot be maintained.

## Exact anti-overclaim rules

- BigAI stays `behavioral reconstruction`.
- Do not collapse context loss, stale memory, workspace drift, branch/path corruption, session persistence failure, and runtime memory pressure into one bucket.
- Runtime allocator-memory failures must remain distinct from coding-agent context/memory failures.
- Do not collapse model/harness/environment/benchmark-task-contract causes when mixed.

## Exact coverage reporting expectations

Include:

- `coverage_used`
- `coverage_not_yet_used`
- `support_artifacts_used`
- `support_artifacts_requested_or_deferred`
- `coverage_register_updates_needed`

## Dirty-worktree rule

- Expect unrelated dirty files and concurrent Deep Synthesis outputs.
- Do not stop for a dirty worktree alone.
- Edit only assigned Wave 03 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with the assigned write scope.

