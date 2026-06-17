# Wave 04 Support Task Templates

Use these templates when a main Wave 04 lane wants bounded support help.

Always pair them with:

- `prompts/deep_synthesis_support_subagent_prompt.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/inputs/support_subagent_rules.md`

Every support task must specify:

- exact bounded task
- exact path scope
- exact stop condition
- exact output path

Support artifacts are not final synthesis.

## 1. Trajectory lane template

- task shape:
  - inventory or matrix over specific Wave 04 trajectory slices
- input scope:
  - selected `research/sources/trajectories/...` families only
- stop condition:
  - stop after the requested runs or path families are fully routed into the matrix or table
- output naming pattern:
  - `trajectory_support_<topic>.md`
- reminder:
  - do not promote mechanism claims; produce reusable support structure only

Recommended Wave 04 uses:

- `trajectory_support_context_workspace_matrix.md`
- `trajectory_support_memory_state_drift_cases.md`
- `trajectory_support_branch_worktree_state_table.md`
- `trajectory_support_run_to_source_link_map.md`

## 2. Source lane template

- task shape:
  - bounded subsystem map or file-discovery map for a named family
- input scope:
  - selected `research/sources/codebases/...`, `blocks/`, `runner/`, or `evals/` paths only
- stop condition:
  - stop once the requested subsystem or route map is complete and path-backed
- output naming pattern:
  - `codebase_support_<topic>.md`
- reminder:
  - do not convert archive hints into source-backed claims

Recommended Wave 04 uses:

- `codebase_support_context_state_map.md`
- `codebase_support_workspace_artifact_map.md`
- `codebase_support_compaction_handoff_map.md`
- `codebase_support_claw_code_runtime_state_map.md`

## 3. Literature lane template

- task shape:
  - bounded cluster, routing, or terminology grouping for the active domain
- input scope:
  - selected `research/sources/papers/` and `research/sources/docs/` paths only
- stop condition:
  - stop once the requested cluster or routing artifact is complete
- output naming pattern:
  - `literature_support_<topic>.md`
- reminder:
  - do not treat the cluster itself as the final lane judgment

Recommended Wave 04 uses:

- `literature_support_context_memory_cluster.md`
- `literature_support_workspace_artifact_cluster.md`
- `literature_support_compaction_resume_terms.md`

## 4. Informal lane template

- task shape:
  - bounded issue, postmortem, or informal cluster map for one Wave 04 pressure family
- input scope:
  - selected `research/sources/informal/`, `research/sources/issues/`, and `research/sources/postmortems/` paths only
- stop condition:
  - stop once the cluster is routed and weak versus strong evidence is separated
- output naming pattern:
  - `informal_support_<topic>.md`
- reminder:
  - do not let complaint clustering become promoted synthesis by itself

Recommended Wave 04 uses:

- `informal_support_context_state_issue_cluster.md`
- `informal_support_stale_resume_cluster.md`
- `informal_support_workspace_repo_hygiene_cluster.md`

## Optional eval template only if the lane is explicitly reactivated

- task shape:
  - bounded state-contract or evaluator-state route map
- input scope:
  - selected `research/sources/benchmarks/`, local `evals/`, or eval-code paths only
- stop condition:
  - stop once the requested evaluator-state map is complete
- output naming pattern:
  - `eval_support_<topic>.md`
- reminder:
  - do not launch by default in Wave 04

Recommended Wave 04 use if reactivated:

- `eval_support_state_contract_map.md`
