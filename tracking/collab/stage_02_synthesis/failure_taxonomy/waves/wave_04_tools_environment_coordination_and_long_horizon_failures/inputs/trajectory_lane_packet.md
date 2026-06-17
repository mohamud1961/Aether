# Failure Taxonomy Wave 04 Trajectory Lane Packet

Use this packet for the Wave 04 `trajectory/failure analyst`.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_trajectory_failure_analyst_prompt.md`
3. this file

## Exact role

- `trajectory/failure analyst`

## Exact objective for Wave 04

Produce behavior-anchored failure attribution for `tools_environment_coordination_and_long_horizon_failures`.

You must synthesize failures in:

- tool-gateway mismatch
- cwd/path/workspace contract failure
- permission-policy/runtime mismatch
- process-lifecycle and cancellation breakdown
- role-handoff/delegation mismatch and replanning stall
- timeout-heavy long-horizon degradation

This is a failure-taxonomy wave, not a generic tools/orchestration recap.

## Exact files to read first

1. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/brief.md`
2. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/inputs/support_subagent_rules.md`
3. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/README.md`
4. `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
5. `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
6. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
7. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_PHASE_AND_WAVE_OPERATING_PLAN.md`
8. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
9. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/adjudication/checklist_adjudicator.md`
10. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/synthesis/principal_synthesis.md`
11. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/synthesis/principal_synthesis.md`

Then read required trajectory targets:

- `research/sources/trajectories/BigAI/cancel-async-tasks/`
- `research/sources/trajectories/deepagents/cancel-async-tasks/`
- `research/sources/trajectories/terminus-kira/cancel-async-tasks/`
- `research/sources/trajectories/BigAI/headless-terminal/`
- `research/sources/trajectories/deepagents/headless-terminal/`
- `research/sources/trajectories/BigAI/extract-moves-from-video/`
- `research/sources/trajectories/terminus-kira/extract-moves-from-video/`
- `research/analysis/bigai_trace_layer/output/runs/prove-plus-comm/`
- `research/analysis/bigai_trace_layer/output/runs/cobol-modernization/`
- `research/analysis/bigai_trace_layer/output/runs/openssl-selfsigned-cert/`
- timeout-heavy pressure in `research/analysis/bigai_trace_layer/output/answered_questions.md`

## Exact required dossier updates

- `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/planning_and_replanning.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/delegation_and_role_separation.md`
- `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/tools_environment_permissions.md`
- `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/planning_orchestration_and_interactions.md`

## Exact required case-study updates

- `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/prove_plus_comm.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/cobol_modernization.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/openssl_selfsigned_cert.md`

## Exact output path

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/trajectory_failure_analyst.md`

Follow-up outputs must use:

- `.../trajectory_failure_analyst__followup_01.md`
- `.../trajectory_failure_analyst__followup_02.md`
- `.../trajectory_failure_analyst__revision_01.md`

## Exact support artifacts this lane may request

- `trajectory_support_tool_coordination_failure_matrix.md`
- `trajectory_support_long_horizon_failure_timeline.md`

## Exact stop conditions

Stop and hand back if trajectory evidence is too thin for honest attribution, or if mixed-cause separation cannot be maintained.

## Exact anti-overclaim rules

- BigAI stays `behavioral reconstruction`.
- Keep terminal-first and single-agent baselines visible as comparators.
- Do not collapse tool gateway mismatch, permission/runtime mismatch, path/cwd failure, cancellation failure, delegation mismatch, replanning stall, and timeout degradation into one bucket.
- Do not collapse model/harness/environment/benchmark-pressure causes when evidence is mixed.

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
- Edit only assigned Wave 04 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with assigned write scope.

