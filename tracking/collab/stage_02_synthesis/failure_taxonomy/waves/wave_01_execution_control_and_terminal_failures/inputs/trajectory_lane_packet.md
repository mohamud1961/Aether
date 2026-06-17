# Failure Taxonomy Wave 01 Trajectory Lane Packet

Use this packet for the Wave 01 `trajectory/failure analyst`.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_trajectory_failure_analyst_prompt.md`
3. this file

## Exact role

- `trajectory/failure analyst`

## Exact objective for Wave 01

Produce the behavior-anchored Wave 01 failure synthesis for `execution_control_and_terminal_failures`.

You must synthesize recurring failure attribution for:

- execution-control loss
- terminal-grounding loss
- process lifecycle failure (wait/kill/interrupt/cancel)
- timeout and stall failure
- false-success and repo-state/control drift

This lane must synthesize failure attribution, not just list bad runs.

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

Then read required trajectory targets:

- `research/sources/trajectories/BigAI/extract-moves-from-video/`
- `research/sources/trajectories/deepagents/extract-moves-from-video/`
- `research/sources/trajectories/terminus-kira/extract-moves-from-video/`
- `research/sources/trajectories/BigAI/cancel-async-tasks/`
- `research/sources/trajectories/deepagents/cancel-async-tasks/`
- `research/sources/trajectories/terminus-kira/cancel-async-tasks/`
- `research/sources/trajectories/BigAI/db-wal-recovery/`
- `research/sources/trajectories/deepagents/db-wal-recovery/`
- `research/sources/trajectories/terminus-kira/db-wal-recovery/`
- `research/analysis/bigai_trace_layer/output/answered_questions.md`

## Exact required dossier updates

- `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/tool_use_and_gateways.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/verification_and_replay.md`
- `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/execution_control_and_terminal_failures.md`

## Exact required case-study updates

- `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/db_wal_recovery.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`

## Exact output path

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/trajectory_failure_analyst.md`

Follow-up or correction outputs must use:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/trajectory_failure_analyst__followup_01.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/trajectory_failure_analyst__followup_02.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/trajectory_failure_analyst__revision_01.md`

## Exact support artifacts this lane may request

- `trajectory_support_failure_timeline.md`
- `trajectory_support_terminal_failure_matrix.md`

Support files must be written under:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/`

## Exact stop conditions

Stop and return control to the principal if:

- required trajectory slices are missing enough to block honest attribution
- you cannot separate failure symptom from likely cause
- you cannot distinguish harness, model, environment, and benchmark-blindness contributions
- you would rely on organizer routing instead of direct path accounting

## Exact anti-overclaim rules

- Keep BigAI explicitly at `behavioral reconstruction`.
- Do not collapse model weakness, harness weakness, environment fragility, and benchmark blindness into one cause when evidence is mixed.
- Do not promote timeout as single-cause without checking process lifecycle, tool call sequence, and verifier presence.
- Do not treat support artifacts as final claims.

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
- Do not merge inline proof, external grader, replay gate, and final acceptance into one layer.
- Robust permission safety remains under-evidenced at trajectory level.
- Environment discovery remains exploratory.
- Explicit role-separated orchestration remains under-saturated outside BigAI-heavy evidence.
- Organizer remains weaker than direct path accounting while `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` stays empty.
