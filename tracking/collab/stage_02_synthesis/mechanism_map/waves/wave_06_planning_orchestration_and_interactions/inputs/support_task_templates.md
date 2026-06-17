# Wave 06 Support Task Templates

Use these templates when a Wave 06 main lane needs bounded support help.

Always pair with:

- `prompts/deep_synthesis_support_subagent_prompt.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/inputs/support_subagent_rules.md`

Support artifacts are not final synthesis.

## Trajectory lane template

- task shape:
  - bounded run timeline, interaction map, or role-handoff table for Wave 06 trajectory families
- input scope:
  - selected paths under `research/sources/trajectories/` and `research/analysis/bigai_trace_layer/output/runs/`
- stop condition:
  - stop when requested slices are fully mapped with explicit path-backed entries
- output naming pattern:
  - `trajectory_support_<topic>.md`
- reminder:
  - do not promote mechanism claims; produce reusable support structure only

Typical Wave 06 outputs:

- `trajectory_support_planning_timeline.md`
- `trajectory_support_delegation_interaction_map.md`

## Source lane template

- task shape:
  - bounded subsystem map, file-discovery map, or route map for planner runtime and delegation controls
- input scope:
  - selected paths under `research/sources/codebases/`, `blocks/`, `runner/`, and `evals/`
- stop condition:
  - stop when requested subsystem map is complete and path-backed
- output naming pattern:
  - `codebase_support_<topic>.md`
- reminder:
  - support maps do not equal promoted synthesis claims

Typical Wave 06 outputs:

- `codebase_support_planner_runtime_map.md`
- `codebase_support_subagent_delegation_map.md`

## Literature lane template

- task shape:
  - bounded cluster, theme routing, or terminology grouping for planning/delegation/interaction doctrine
- input scope:
  - selected paths under `research/sources/papers/` and `research/sources/docs/`
- stop condition:
  - stop when requested cluster/route map is complete and path-backed
- output naming pattern:
  - `literature_support_<topic>.md`
- reminder:
  - cluster artifacts support synthesis; they do not replace it

Typical Wave 06 output:

- `literature_support_planning_delegation_cluster.md`

## Informal lane template

- task shape:
  - bounded issue/postmortem cluster map for one orchestration-failure family
- input scope:
  - selected paths under `research/sources/informal/`, `research/sources/issues/`, and `research/sources/postmortems/`
- stop condition:
  - stop when requested cluster is routed with strong/weak evidence separation
- output naming pattern:
  - `informal_support_<topic>.md`
- reminder:
  - support clustering is not final mechanism judgment

Typical Wave 06 output:

- `informal_support_orchestration_failure_cluster.md`

## Optional eval-lane support if explicitly reactivated

- task shape:
  - bounded benchmark role-contract map for planner/verifier/delegation interactions
- input scope:
  - selected paths under `research/sources/papers/`, `research/sources/docs/`, and `evals/`
- stop condition:
  - stop when role-contract map is complete and path-backed
- output naming pattern:
  - `eval_support_<topic>.md`
- reminder:
  - eval remains inactive unless principal explicitly reactivates it

Potential output:

- `eval_support_role_contract_map.md`

