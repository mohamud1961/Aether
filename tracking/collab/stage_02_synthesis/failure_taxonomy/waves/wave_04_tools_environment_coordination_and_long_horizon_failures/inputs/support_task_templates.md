# Failure Taxonomy Wave 04 Support Task Templates

Use with:

- `prompts/deep_synthesis_support_subagent_prompt.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/inputs/support_subagent_rules.md`

Support artifacts are not final claims.

## Trajectory template

- task shape: tool/coordination failure matrix and long-horizon timeline extraction
- input scope: selected trajectory and BigAI analysis paths
- stop condition: requested matrix/timeline complete and path-backed
- output naming: `trajectory_support_<topic>.md`

Targets:

- `trajectory_support_tool_coordination_failure_matrix.md`
- `trajectory_support_long_horizon_failure_timeline.md`

## Source template

- task shape: tool/environment and orchestration failure subsystem maps
- input scope: selected codebase, `blocks/`, `runner/`, `evals/`
- stop condition: requested map complete and path-backed
- output naming: `codebase_support_<topic>.md`

Targets:

- `codebase_support_tool_environment_failure_map.md`
- `codebase_support_orchestration_failure_map.md`

## Literature template

- task shape: tool/orchestration failure-pressure clustering
- input scope: papers_text and docs paths
- stop condition: cluster complete and path-backed
- output naming: `literature_support_<topic>.md`

Target:

- `literature_support_tools_orchestration_failure_cluster.md`

## Informal template

- task shape: long-horizon tooling/coordination contradiction clustering
- input scope: informal, issues, postmortems paths
- stop condition: cluster complete with strong/weak separation
- output naming: `informal_support_<topic>.md`

Target:

- `informal_support_long_horizon_tooling_failure_cluster.md`

## Optional eval template (only if reactivated)

- task shape: benchmark time/replay/tool contract map
- input scope: benchmark/eval paths only when reactivation is approved
- stop condition: map complete and path-backed
- output naming: `eval_support_<topic>.md`

Target:

- `eval_support_benchmark_time_contract_map.md`

## Dirty-worktree rule

- Expect unrelated dirty files and concurrent Deep Synthesis outputs.
- Do not stop for a dirty worktree alone.
- Edit only assigned Wave 04 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with assigned write scope.

