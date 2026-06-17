# Failure Taxonomy Wave 01 Contradiction Packet

Use this packet for the primary contradiction review in Wave 01.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_contradiction_analyst_prompt.md`
3. this file

## Exact files to read

Read first:

1. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/brief.md`
2. `tracking/collab/stage_02_synthesis/failure_taxonomy/brief.md`
3. `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
4. `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
5. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
6. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
7. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
8. `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
9. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/synthesis/principal_synthesis.md`
10. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
11. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/synthesis/principal_synthesis.md`
12. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/synthesis/principal_synthesis.md`

Then read all primary Wave 01 outputs:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/trajectory_failure_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_source_reconstruction_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/literature_papers_docs_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/informal_issues_postmortems_analyst.md`

Read any support artifacts materially cited by those lanes.

## Exact output path

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/contradiction_analyst.md`

## Exact Wave 01 attack surface

Attack these directly:

- fake execution-control certainty not supported by trajectory/source evidence
- model-only blame that ignores harness, environment, or benchmark-blindness pressure
- harness-only blame that ignores model limits
- timeout claims missing process lifecycle or cancellation context
- false-success claims without verifier/benchmark contract checks
- silent eval-lane reasoning while eval is inactive
- support artifacts treated as promoted final claims
- BigAI treated beyond `behavioral reconstruction`

## What is a blocker vs carry-forward warning

Return `blocked` if:

- core failure attribution is structurally unsupported
- claims are causally collapsed despite mixed evidence
- wave framing would mislead downstream artifact work

Return `pass_with_warnings` if:

- wave is materially useful
- mixed-cause uncertainty remains explicit and tracked

Return `pass` only if:

- attribution is supported, reconciled, and uncertainty is honest

## Explicit distinction to enforce

- wave acceptance is not artifact completion
- accepted Wave 01 output can still leave `failure_taxonomy` incomplete
- carry-forward warnings are part of acceptance, not a formatting defect

## Explicit mixed-cause anti-collapse warning

Do not collapse model, harness, environment, and benchmark-blindness into one cause when evidence is mixed.

