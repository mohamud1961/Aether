# Wave 05 Contradiction Packet

Use this packet for the primary contradiction review in Wave 05.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_contradiction_analyst_prompt.md`
3. this file

## Exact files to read

Read first:

1. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/brief.md`
2. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
3. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
4. `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
5. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`
6. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`

Then read all primary Wave 05 first-pass outputs:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_failure_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/codebase_source_reconstruction_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/literature_papers_docs_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/informal_issues_postmortems_analyst.md`

Read any support outputs materially cited by those lanes.

## Exact output path

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/contradiction_analyst.md`

## Exact Wave 05 attack surface

Attack these directly:

- fake tool-gateway sophistication without source or behavior support
- fake sandbox or permission safety claims
- hidden environment assumptions that are not validated in-run
- cwd/workdir/path/process-discipline overclaims
- browser/tool prestige overclaims
- source/trajectory mismatches on tool or permission behavior
- silent eval-lane reasoning while eval is inactive
- support artifacts used as promoted claims
- BigAI treated beyond `behavioral reconstruction`

## What is a blocker vs carry-forward warning

Return `blocked` if:

- core promoted claims are structurally unsupported
- required evidence classes are missing for the promoted families
- wave framing is misleading enough to harm downstream synthesis

Return `pass_with_warnings` if:

- wave results are materially useful
- but unresolved limits remain that can be explicitly carried forward

Return `pass` only if:

- claims are supported, reconciled, and minimally distorted by unresolved gaps

## Explicit distinction to enforce

- wave acceptance is not artifact completion
- accepted Wave 05 output can still leave `mechanism_map` incomplete
- carry-forward warnings are part of acceptance, not a formatting defect

## Carry-forward caution enforcement

Keep these explicit:

- Wave 03 cautions: BigAI behavioral reconstruction, restart/resume under-evidenced, organizer weak
- Wave 04 cautions: artifact-first baseline, source-capacity vs behavior-exercise gap, anti-flattening of mechanism families
