# Wave 05 Support Sub-Agent Rules

Use this addendum when a Wave 05 main lane wants bounded support help.

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

## Recommended support tasks for Wave 05

Trajectory lane:

- tool and environment matrix
- permission and approval boundary case table
- browser or terminal substrate comparison table
- run-to-source link map

Source lane:

- tool gateway map
- environment and sandbox path map
- permission and approval path map
- browser and terminal substrate map

Literature lane:

- tool use and gateway cluster
- environment and permission docs cluster
- approval and sandbox terminology grouping

Informal lane:

- sandboxing and approval issue cluster
- browser or tool friction cluster
- cwd, workdir, and environment mismatch cluster

Eval lane if reactivated:

- tool contract map
- permission-sensitive benchmark map

## Required output rule

Every support artifact must be saved under:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/`

Use descriptive names such as:

- `trajectory_support_tool_environment_matrix.md`
- `trajectory_support_permission_boundary_cases.md`
- `codebase_support_tool_gateway_map.md`
- `codebase_support_environment_permission_map.md`
- `literature_support_tool_gateway_cluster.md`
- `informal_support_sandbox_permission_cluster.md`
- `eval_support_tool_contract_map.md`

## Lane responsibility

The owning main lane must:

- launch the support task with a precise prompt
- read the support artifact
- cite it explicitly
- decide what it means

Support outputs help the lane.
They do not close the lane.
