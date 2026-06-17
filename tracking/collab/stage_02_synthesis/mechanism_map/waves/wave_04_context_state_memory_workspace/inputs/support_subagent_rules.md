# Wave 04 Support Sub-Agent Rules

Use this addendum when a Wave 04 main lane wants bounded support help.

## Core mandate

Support sub-agents are standard lane infrastructure for this wave.

Their job is to:

- compact context
- produce reusable support artifacts
- improve route finding and coverage discipline

Their job is not to:

- replace a main lane
- write the promoted mechanism claims
- decide the wave verdict

## Use the reusable prompt

When launching a support sub-agent, use:

- `prompts/deep_synthesis_support_subagent_prompt.md`

The calling lane must provide:

- exact bounded task
- exact path scope
- exact stop condition
- exact output path

## Recommended support tasks for Wave 04

Trajectory lane:

- context and workspace matrix
- memory-write and stale-memory case table
- branch and worktree state table
- run-to-source link map

Source lane:

- context and state subsystem map
- compaction, summary, and handoff path map
- workspace and artifact discipline path map
- `claw-code` runtime state path map

Literature lane:

- context and memory paper cluster
- workspace and artifact discipline cluster
- compaction and resume terminology grouping

Informal lane:

- context flooding and compaction issue cluster
- stale resume and state drift issue cluster
- workspace and repo-state hygiene cluster

Eval lane if reactivated:

- context and state contract map
- local eval hook and state comparator map

## Required output rule

Every support artifact must be saved under:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/`

Use descriptive names such as:

- `trajectory_support_context_workspace_matrix.md`
- `trajectory_support_memory_state_drift_cases.md`
- `codebase_support_context_state_map.md`
- `codebase_support_workspace_artifact_map.md`
- `literature_support_context_memory_cluster.md`
- `informal_support_context_state_issue_cluster.md`
- `eval_support_state_contract_map.md`

## Lane responsibility

The owning main lane must:

- launch the support task with a precise prompt
- read the support artifact
- cite it explicitly
- decide what it means

Support outputs help the lane.
They do not close the lane.
