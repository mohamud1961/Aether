# Failure Taxonomy Wave 01 Codebase Lane Packet

Use this packet for the Wave 01 `codebase/source-reconstruction analyst`.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_codebase_source_reconstruction_analyst_prompt.md`
3. this file

## Exact role

- `codebase/source-reconstruction analyst`

## Exact objective for Wave 01

Produce the implementation-grounded Wave 01 failure synthesis for `execution_control_and_terminal_failures`.

You must synthesize recurrent failure attribution for:

- execution-loop breakdown
- interrupt/cancel/kill failure
- timeout and cleanup failure
- verifier omission and false-success surfaces
- repo-state/control drift under terminal workflows

This lane must synthesize failure attribution, not just list modules.

## Exact files to read first

1. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/brief.md`
2. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/inputs/support_subagent_rules.md`
3. `tracking/collab/stage_02_synthesis/failure_taxonomy/brief.md`
4. `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
5. `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
6. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
7. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
8. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
9. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
10. `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
11. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/synthesis/principal_synthesis.md`
12. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
13. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/synthesis/principal_synthesis.md`
14. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/synthesis/principal_synthesis.md`

Then read required source surfaces:

- `research/sources/codebases/deepagents/`
- `research/sources/codebases/KIRA/`
- `research/sources/codebases/a-evolve/`
- `research/sources/codebases/quarantine/claw-code/`
- `blocks/`
- `runner/`
- `evals/`

## Exact required dossier updates

- `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/tool_use_and_gateways.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/verification_and_replay.md`
- `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/execution_control_and_terminal_failures.md`

## Exact required case-study updates where relevant

- `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/db_wal_recovery.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`

## Exact output path

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_source_reconstruction_analyst.md`

Follow-up or correction outputs must use:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_source_reconstruction_analyst__followup_01.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_source_reconstruction_analyst__followup_02.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_source_reconstruction_analyst__revision_01.md`

## Exact support artifacts this lane may request

- `codebase_support_execution_failure_map.md`
- `codebase_support_interrupt_cancellation_map.md`

Support files must be written under:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/`

## Exact stop conditions

Stop and return control to the principal if:

- required source families are too incomplete for cross-family attribution
- you cannot reconcile source mechanisms with trajectory failure symptoms
- source coverage cannot separate mirrored systems from exploratory archive pressure
- eval lane activation is required to explain core attribution

## Exact anti-overclaim rules

- Keep BigAI out of source-backed implementation claims.
- Do not infer robust execution control from API presence alone.
- Do not collapse scheduler/planner/runtime/verification surfaces into one cause.
- Do not collapse model, harness, environment, and benchmark-blindness into one cause when evidence is mixed.
- Do not treat support artifacts as final synthesis.

## Exact coverage reporting expectations

Include all of:

- `coverage_used`
- `coverage_not_yet_used`
- `evidence_classes_touched`
- `priority_sources_not_yet_read`
- `support_artifacts_used`
- `support_artifacts_requested_or_deferred`
- `coverage_register_updates_needed`
- `required_dossier_updates`

## Exact carry-forward cautions inherited from mechanism_map

- BigAI remains `behavioral reconstruction`.
- Restart/resumability remains under-evidenced behaviorally.
- DeepAgents inline verifier behavior in `db-wal-recovery` is not yet clearly mirrored framework verifier code.
- Robust permission safety remains under-evidenced at trajectory level.
- Environment discovery remains exploratory.
- Role-separated orchestration evidence remains uneven outside BigAI-heavy slices.
- Organizer remains secondary to direct path accounting.

