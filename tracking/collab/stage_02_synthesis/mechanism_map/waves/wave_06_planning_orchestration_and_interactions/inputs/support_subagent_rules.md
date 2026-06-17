# Wave 06 Support Sub-Agent Rules

Use this addendum when a Wave 06 main lane wants bounded support help.

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

## Recommended support tasks for Wave 06

Trajectory lane:

- planning and replanning timeline
- delegation and interaction map
- role-handoff sequence table
- single-agent versus orchestrated-run comparison table

Source lane:

- planner-runtime map
- subagent and delegation map
- role-separation and interaction-contract map
- orchestration state or handoff map

Literature lane:

- planning and replanning cluster
- delegation and role-separation cluster
- interaction-contract terminology grouping

Informal lane:

- orchestration failure cluster
- delegation mismatch cluster
- planner drift and replan trigger cluster

Eval lane if reactivated:

- planner or verifier role-contract map
- orchestration-sensitive benchmark map

## Required output rule

Every support artifact must be saved under:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/`

Use descriptive names such as:

- `trajectory_support_planning_timeline.md`
- `trajectory_support_delegation_interaction_map.md`
- `codebase_support_planner_runtime_map.md`
- `codebase_support_subagent_delegation_map.md`
- `literature_support_planning_delegation_cluster.md`
- `informal_support_orchestration_failure_cluster.md`
- `eval_support_role_contract_map.md`

## Lane responsibility

The owning main lane must:

- launch the support task with a precise prompt
- read the support artifact
- cite it explicitly
- decide what it means

Support outputs help the lane.
They do not close the lane.
