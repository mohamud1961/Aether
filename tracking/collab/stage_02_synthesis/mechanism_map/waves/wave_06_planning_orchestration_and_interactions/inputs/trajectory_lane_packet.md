# Wave 06 Trajectory Lane Packet

Use this packet for the Wave 06 `trajectory/failure analyst`.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_trajectory_failure_analyst_prompt.md`
3. this file

## Exact role

- `trajectory/failure analyst`

## Exact objective for Wave 06

Produce the behavior-anchored Wave 06 synthesis for `planning_orchestration_and_interactions`.

You must synthesize how systems actually:

- plan and replan across multi-step work
- delegate and bound subagent work
- separate planner/executor/verifier or role-specific responsibilities
- enforce interaction contracts during handoffs
- detect and recover from coordination drift or hidden coupling

This lane must synthesize mechanism structure. Do not return only notes or timeline fragments.

## Exact files to read first

1. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/brief.md`
2. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/inputs/support_subagent_rules.md`
3. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
4. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
5. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
6. `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
7. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/synthesis/principal_synthesis.md`
8. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`

Then read required trajectory targets from the wave brief:

- `research/analysis/bigai_trace_layer/output/runs/prove-plus-comm/`
- `research/analysis/bigai_trace_layer/output/runs/cobol-modernization/`
- `research/analysis/bigai_trace_layer/output/runs/openssl-selfsigned-cert/`
- `research/sources/trajectories/BigAI/`

Optional long-tail pressure:

- `research/sources/trajectories/*/protein-assembly/`
- `research/sources/trajectories/*/large-scale-text-editing/`

## Exact required dossier updates

- `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/planning_and_replanning.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/delegation_and_role_separation.md`
- `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/planning_orchestration_and_interactions.md`

## Exact required case-study updates

- `tracking/collab/stage_02_synthesis/trajectory_case_studies/prove_plus_comm.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/cobol_modernization.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/openssl_selfsigned_cert.md`

## Exact output path

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/trajectory_failure_analyst.md`

Follow-up or correction outputs must use:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/trajectory_failure_analyst__followup_01.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/trajectory_failure_analyst__followup_02.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/trajectory_failure_analyst__revision_01.md`

## Exact support artifacts this lane may request

- `trajectory_support_planning_timeline.md`
- `trajectory_support_delegation_interaction_map.md`

Support files must be written under:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/`

## Exact stop conditions

Stop and return control to the principal if:

- required trajectory slices are missing or unreadable enough to block honest synthesis
- the lane would rely on organizer routing instead of direct path accounting
- the lane cannot separate observation from inference for promoted claims
- the lane would need eval activation to answer the core wave question

## Exact anti-overclaim rules

- Keep BigAI explicitly as `behavioral reconstruction`.
- Do not promote orchestration quality from single successes without failure pressure.
- Do not collapse planning, delegation, and interaction contracts into one vague family.
- Do not treat support artifacts as final promoted claims.
- Do not treat role labels as proof of true role separation.

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

## Exact carry-forward cautions from Waves 03, 04, and 05

- Wave 03: keep restart/resumability under-evidenced; do not over-promote.
- Wave 03: keep BigAI as `behavioral reconstruction`.
- Wave 03: organizer remains secondary to direct path accounting.
- Wave 04: keep artifact-first baseline visible against richer orchestration rhetoric.
- Wave 04: keep source-visible capacity separate from behavior-visible exercise.
- Wave 04: do not flatten distinct mechanism surfaces into one merged family.
- Wave 05: robust permission safety is still under-evidenced behaviorally.
- Wave 05: environment discovery remains exploratory.
- Wave 05: keep terminal-first baseline visible while evaluating richer orchestration stacks.
- Wave 05: keep missing `trajectory_case_studies/headless_terminal.md` visible as carry-forward support debt.
