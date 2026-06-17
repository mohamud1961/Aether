# Failure Taxonomy Wave 03 Support Task Templates

Use with:

- `prompts/deep_synthesis_support_subagent_prompt.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/support_subagent_rules.md`

Support artifacts are not final claims.

## Trajectory template

- task shape: context/workspace failure matrix and state-drift case extraction
- input scope: selected trajectory paths and BigAI analysis paths
- stop condition: requested matrix/cases complete and path-backed
- output naming: `trajectory_support_<topic>.md`

Targets:

- `trajectory_support_context_workspace_failure_matrix.md`
- `trajectory_support_memory_state_drift_cases.md`

## Source template

- task shape: context/state/workspace persistence subsystem maps
- input scope: selected codebase, `blocks/`, `runner/`, `evals/`
- stop condition: requested map complete and path-backed
- output naming: `codebase_support_<topic>.md`

Targets:

- `codebase_support_context_state_failure_map.md`
- `codebase_support_workspace_persistence_map.md`

## Literature template

- task shape: context/memory/workspace failure-pressure clustering
- input scope: papers_text and docs paths
- stop condition: cluster complete and path-backed
- output naming: `literature_support_<topic>.md`

Target:

- `literature_support_context_memory_failure_cluster.md`

## Informal template

- task shape: context/workspace failure contradiction clustering
- input scope: informal, issues, postmortems paths
- stop condition: cluster complete with strong/weak separation
- output naming: `informal_support_<topic>.md`

Target:

- `informal_support_context_workspace_failure_cluster.md`

## Optional eval template (only if reactivated)

- task shape: state-contract/replay/workspace expectation map
- input scope: benchmarks/evals only when reactivation is approved
- stop condition: map complete and path-backed
- output naming: `eval_support_<topic>.md`

Target:

- `eval_support_state_contract_map.md`

## Dirty-worktree rule

- Expect unrelated dirty files and concurrent Deep Synthesis outputs.
- Do not stop for a dirty worktree alone.
- Edit only assigned Wave 03 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with the assigned write scope.

