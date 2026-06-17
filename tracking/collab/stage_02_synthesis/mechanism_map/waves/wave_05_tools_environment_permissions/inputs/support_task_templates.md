# Wave 05 Support Task Templates

Use these templates when a Wave 05 main lane needs bounded support help.

Always pair with:

- `prompts/deep_synthesis_support_subagent_prompt.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/inputs/support_subagent_rules.md`

Support artifacts are not final synthesis.

## Trajectory lane template

- task shape:
  - bounded run inventory, matrix, or case table for Wave 05 trajectory families
- input scope:
  - selected paths under `research/sources/trajectories/` only
- stop condition:
  - stop when requested slices are fully mapped with explicit path-backed entries
- output naming pattern:
  - `trajectory_support_<topic>.md`
- reminder:
  - do not promote mechanism claims; produce reusable support structure only

Typical Wave 05 outputs:

- `trajectory_support_tool_environment_matrix.md`
- `trajectory_support_permission_boundary_cases.md`
- `trajectory_support_browser_terminal_substrate_table.md`

## Source lane template

- task shape:
  - bounded subsystem map, file-discovery map, or route map for tool/environment/permission surfaces
- input scope:
  - selected paths under `research/sources/codebases/`, `blocks/`, `runner/`, and `evals/`
- stop condition:
  - stop when requested subsystem map is complete and path-backed
- output naming pattern:
  - `codebase_support_<topic>.md`
- reminder:
  - support maps do not equal promoted synthesis claims

Typical Wave 05 outputs:

- `codebase_support_tool_gateway_map.md`
- `codebase_support_environment_permission_map.md`
- `codebase_support_approval_boundary_map.md`

## Literature lane template

- task shape:
  - bounded cluster, theme routing, or terminology grouping for formal sources
- input scope:
  - selected paths under `research/sources/papers/` and `research/sources/docs/`
- stop condition:
  - stop when requested cluster/route map is complete and path-backed
- output naming pattern:
  - `literature_support_<topic>.md`
- reminder:
  - cluster artifacts support synthesis; they do not replace it

Typical Wave 05 outputs:

- `literature_support_tool_gateway_cluster.md`
- `literature_support_environment_permission_cluster.md`
- `literature_support_approval_sandbox_terms.md`

## Informal lane template

- task shape:
  - bounded issue/postmortem cluster map for one contradiction-pressure family
- input scope:
  - selected paths under `research/sources/informal/`, `research/sources/issues/`, and `research/sources/postmortems/`
- stop condition:
  - stop when requested cluster is routed with strong/weak evidence separation
- output naming pattern:
  - `informal_support_<topic>.md`
- reminder:
  - support clustering is not final mechanism judgment

Typical Wave 05 outputs:

- `informal_support_sandbox_permission_cluster.md`
- `informal_support_tool_friction_cluster.md`
- `informal_support_cwd_workdir_env_mismatch_cluster.md`
