# Failure Taxonomy Wave 02 Support Task Templates

Use with:

- `prompts/deep_synthesis_support_subagent_prompt.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/inputs/support_subagent_rules.md`

Support artifacts are not final claims.

## Trajectory lane template

- task shape: run-level false-completion/recovery matrices
- input scope: selected trajectory and BigAI analysis paths
- stop condition: requested matrix complete and path-backed
- output naming: `trajectory_support_<topic>.md`

Targets:

- `trajectory_support_false_completion_matrix.md`
- `trajectory_support_recovery_failure_matrix.md`

## Source lane template

- task shape: verifier/recovery/cleanup subsystem maps
- input scope: selected codebase, `blocks/`, `runner/`, `evals/`
- stop condition: requested map complete and path-backed
- output naming: `codebase_support_<topic>.md`

Targets:

- `codebase_support_verifier_recovery_failure_map.md`
- `codebase_support_completion_cleanup_map.md`

## Literature lane template

- task shape: formal failure-pressure clustering
- input scope: `research/sources/papers/papers_text/`, `research/sources/docs/`
- stop condition: cluster complete and path-backed
- output naming: `literature_support_<topic>.md`

Target:

- `literature_support_verification_recovery_failure_cluster.md`

## Informal lane template

- task shape: issue/postmortem false-completion and recovery cluster
- input scope: informal/issues/postmortems paths
- stop condition: cluster complete with strong/weak separation
- output naming: `informal_support_<topic>.md`

Target:

- `informal_support_false_completion_recovery_cluster.md`

## Eval lane template

- task shape: verifier/grader/replay/benchmark contract map
- input scope: benchmarks, eval repos, local evals
- stop condition: contract map complete and path-backed
- output naming: `eval_support_<topic>.md`

Target:

- `eval_support_verifier_benchmark_contract_map.md`

## Dirty-worktree rule

- Expect unrelated dirty files and concurrent Deep Synthesis outputs.
- Do not stop for a dirty worktree alone.
- Edit only assigned Wave 02 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with assigned write scope.

