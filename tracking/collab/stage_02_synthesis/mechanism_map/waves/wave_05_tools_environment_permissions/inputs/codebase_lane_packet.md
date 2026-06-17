# Wave 05 Codebase Lane Packet

Use this packet for the Wave 05 `codebase/source-reconstruction analyst`.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_codebase_source_reconstruction_analyst_prompt.md`
3. this file

## Exact role

- `codebase/source-reconstruction analyst`

## Exact objective for Wave 05

Produce the implementation-grounded Wave 05 synthesis for `tools_environment_permissions`.

You must synthesize where systems implement:

- tool gateways and tool policy surfaces
- environment discovery and preflight checks
- sandboxing and permission boundaries
- approval or escalation controls
- browser and terminal substrate interfaces
- cwd/workdir/path/process handling discipline

This lane must synthesize mechanism families. Do not return only subsystem maps.

## Exact files to read first

1. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/brief.md`
2. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/inputs/support_subagent_rules.md`
3. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
4. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
5. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
6. `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
7. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`
8. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`

Then read the required source surfaces:

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
- `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/tool_use_and_gateways.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md`
- `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/tools_environment_permissions.md`

## Exact required case-study updates where relevant

- `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`

## Exact output path

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/codebase_source_reconstruction_analyst.md`

Follow-up or correction outputs must use:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/codebase_source_reconstruction_analyst__followup_01.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/codebase_source_reconstruction_analyst__followup_02.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/codebase_source_reconstruction_analyst__revision_01.md`

## Exact support artifacts this lane may request

- `codebase_support_tool_gateway_map.md`
- `codebase_support_environment_permission_map.md`
- `codebase_support_approval_boundary_map.md`
- `codebase_support_browser_terminal_substrate_map.md`

Support files must be written under:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/`

## Exact stop conditions

Stop and return control to the principal if:

- required source families are too incomplete for honest cross-family synthesis
- source coverage cannot separate first-class mirrored systems from exploratory archive pressure
- the lane would need eval activation to explain core mechanism structure

## Exact anti-overclaim rules

- Keep BigAI out of source-backed implementation claims.
- Do not convert `src_cod_*` or quarantine hints into first-class facts.
- Do not claim permission safety from configuration presence alone.
- Do not treat browser integration presence as proof of robust environment doctrine.
- Do not flatten sandbox, approval, and cwd/workdir mechanisms into one category.

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

- Wave 03: restart/resumability stays under-evidenced at behavior level.
- Wave 03: BigAI remains `behavioral reconstruction`.
- Wave 03: organizer is not a trusted primary routing surface.
- Wave 04: artifact-first baseline must remain visible.
- Wave 04: source-visible capacity can exceed trajectory-visible exercise.
- Wave 04: keep mechanism splits explicit; avoid merged mega-families.
