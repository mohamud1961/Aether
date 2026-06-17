# Failure Taxonomy Wave 04 Codebase Lane Packet

Use this packet for the Wave 04 `codebase/source-reconstruction analyst`.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_codebase_source_reconstruction_analyst_prompt.md`
3. this file

## Exact role

- `codebase/source-reconstruction analyst`

## Exact objective for Wave 04

Produce source-grounded failure attribution for tool/environment coordination and long-horizon failure regimes.

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

Then read:

- `research/sources/codebases/deepagents/`
- `research/sources/codebases/KIRA/`
- `research/sources/codebases/a-evolve/`
- `research/sources/codebases/quarantine/claw-code/`
- `blocks/`
- `runner/`
- `evals/`

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

## Exact output path

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/codebase_source_reconstruction_analyst.md`

Follow-up outputs must use:

- `.../codebase_source_reconstruction_analyst__followup_01.md`
- `.../codebase_source_reconstruction_analyst__followup_02.md`
- `.../codebase_source_reconstruction_analyst__revision_01.md`

## Exact support artifacts this lane may request

- `codebase_support_tool_environment_failure_map.md`
- `codebase_support_orchestration_failure_map.md`

## Exact stop conditions

Stop and hand back if source visibility is too thin for cross-family attribution or if trajectory-source linkage cannot be made for major claims.

## Exact anti-overclaim rules

- BigAI cannot be used for source-backed claims.
- Do not collapse tool/environment/coordination failure families into one generic orchestration failure.
- Keep terminal-first and single-agent baselines as active comparators.
- Do not collapse model/harness/environment/benchmark-pressure causes when mixed.

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

