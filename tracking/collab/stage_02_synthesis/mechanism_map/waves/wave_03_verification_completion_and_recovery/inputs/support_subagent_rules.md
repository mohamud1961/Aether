# Wave 03 Support Sub-Agent Rules

Use this addendum when a Wave 03 main lane wants bounded support help.

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

## Recommended support tasks for Wave 03

Trajectory lane:

- verification matrix
- false-completion case table
- recovery / rollback / restart table
- run-to-source link map

Source lane:

- verifier and cleanup subsystem map
- restart / resume path map
- archive triage for relevant `src_cod_*` captures

Literature lane:

- verification and completion paper cluster
- completion-contract terminology grouping

Informal lane:

- recovery / resume issue cluster
- false-completion and cleanup postmortem grouping

Eval lane:

- verifier / grader / replay route map
- benchmark contract comparison table

## Required output rule

Every support artifact must be saved under:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/`

Use descriptive names such as:

- `trajectory_support_verification_matrix.md`
- `trajectory_support_false_completion_cases.md`
- `trajectory_support_recovery_restart_table.md`
- `codebase_support_verifier_recovery_map.md`
- `eval_support_verifier_grader_replay_matrix.md`
- `literature_support_verification_cluster.md`
- `informal_support_recovery_issue_cluster.md`

## Lane responsibility

The owning main lane must:

- launch the support task with a precise prompt
- read the support artifact
- cite it explicitly
- decide what it means

Support outputs help the lane.
They do not close the lane.
