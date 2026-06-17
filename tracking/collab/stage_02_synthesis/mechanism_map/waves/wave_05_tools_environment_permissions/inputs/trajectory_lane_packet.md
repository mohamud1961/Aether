# Wave 05 Trajectory Lane Packet

Use this packet for the Wave 05 `trajectory/failure analyst`.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_trajectory_failure_analyst_prompt.md`
3. this file

## Exact role

- `trajectory/failure analyst`

## Exact objective for Wave 05

Produce the behavior-anchored Wave 05 synthesis for `tools_environment_permissions`.

You must synthesize how systems actually:

- discover environment and preconditions
- choose, sequence, and recover tool use
- handle browser versus terminal substrate boundaries
- enforce approval, sandbox, and permission boundaries
- maintain cwd/workdir/path/process discipline
- fail when tool/environment assumptions are wrong

This lane must synthesize mechanism structure. Do not return only notes or run excerpts.

## Exact files to read first

1. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/brief.md`
2. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/inputs/support_subagent_rules.md`
3. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
4. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
5. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
6. `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
7. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`
8. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`

Then read the required trajectory targets from the wave brief:

- `research/sources/trajectories/BigAI/headless-terminal/`
- `research/sources/trajectories/deepagents/headless-terminal/`
- `research/sources/trajectories/terminus-kira/headless-terminal/`
- `research/sources/trajectories/BigAI/extract-moves-from-video/`
- `research/sources/trajectories/deepagents/extract-moves-from-video/`
- `research/sources/trajectories/terminus-kira/extract-moves-from-video/`
- `research/sources/trajectories/BigAI/cancel-async-tasks/`
- `research/sources/trajectories/deepagents/cancel-async-tasks/`
- `research/sources/trajectories/terminus-kira/cancel-async-tasks/`

Optional long-tail pressure:

- `research/sources/trajectories/*/git-multibranch/`

## Exact required dossier updates

- `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/tool_use_and_gateways.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md`
- `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/tools_environment_permissions.md`

## Exact required case-study updates

- `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`

## Exact output path

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_failure_analyst.md`

Follow-up or correction outputs must use:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_failure_analyst__followup_01.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_failure_analyst__followup_02.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_failure_analyst__revision_01.md`

## Exact support artifacts this lane may request

- `trajectory_support_tool_environment_matrix.md`
- `trajectory_support_permission_boundary_cases.md`
- `trajectory_support_browser_terminal_substrate_table.md`
- `trajectory_support_run_to_source_link_map.md`

Support files must be written under:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/`

## Exact stop conditions

Stop and return control to the principal if:

- required trajectory slices are missing or unreadable enough to block honest synthesis
- the lane would rely on organizer routing instead of direct path accounting
- the lane would need to activate eval to answer the core wave question
- the lane cannot separate observation from inference for promoted claims

## Exact anti-overclaim rules

- Keep BigAI explicitly as `behavioral reconstruction`.
- Do not claim permission safety from policy prose without direct behavior evidence.
- Do not collapse tool choice, environment discovery, and approval boundaries into one mechanism.
- Do not treat browser prestige as proof of stronger mechanism quality.
- Do not treat absence of failure in one run window as robust permission or sandbox discipline.

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

## Exact carry-forward cautions from Waves 03 and 04

- Wave 03: keep restart/resumability under-evidenced and do not over-promote it.
- Wave 03: keep BigAI as `behavioral reconstruction`.
- Wave 03: do not treat organizer routing as the primary coverage control.
- Wave 04: keep artifact-first baselines visible against richer architecture rhetoric.
- Wave 04: keep source-visible capacity separate from behavior-visible exercise.
- Wave 04: do not flatten distinct mechanism surfaces into one merged family.
