# Wave 04 Informal Lane Packet

Use this packet for the Wave 04 `informal/issues/postmortems analyst`.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_informal_issues_postmortems_analyst_prompt.md`
3. this file

## Exact role

- `informal/issues/postmortems analyst`

## Exact Wave 04 objective

Produce the contradiction-pressure Wave 04 synthesis for `context_state_memory_workspace`.

You must explain, from informal, issue, and postmortem material:

- where operators complain about context flooding, stale memory, broken resume, state drift, or workspace mess
- which recurring complaints actually pressure the promoted mechanism families
- which complaints are weak, low-credibility, or only philosophy
- where informal pressure reveals contradictions that the trajectory or source lanes might miss

This is a synthesis task, not an issue dump.

## Read these files first

1. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/brief.md`
2. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/inputs/support_subagent_rules.md`
3. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
4. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
5. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
6. `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
7. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
8. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
9. `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/README.md`

## Required direct evidence paths

You must read directly from these path families unless blocked:

- `research/sources/informal/`
- `research/sources/issues/`
- `research/sources/postmortems/`

Priority Wave 04 pressure clusters:

- context flooding and compaction failure
- stale resume and state drift
- workspace and repo-state hygiene
- artifact handoff and stale-memory corruption

## Required dossier updates

- `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/context_state_memory_workspace.md`

## Required case-study updates where relevant

Only request case-study updates when the informal cluster directly pressures:

- `tracking/collab/stage_02_synthesis/trajectory_case_studies/git_multibranch.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/break_filter_js_from_html.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/custom_memory_heap_crash.md`

## Output path

Write exactly here:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/informal_issues_postmortems_analyst.md`

If you need a follow-up, do not overwrite. Use:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/informal_issues_postmortems_analyst__followup_01.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/informal_issues_postmortems_analyst__followup_02.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/informal_issues_postmortems_analyst__revision_01.md`

## Support artifacts you may request

You may request bounded support artifacts such as:

- `informal_support_context_state_issue_cluster.md`
- `informal_support_stale_resume_cluster.md`
- `informal_support_workspace_repo_hygiene_cluster.md`

Support artifacts must be explicit files under:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/`

## Stop conditions

Stop and return control to the principal if any of these are true:

- the lane would mostly repeat low-credibility commentary without usable contradiction pressure
- the informal slice cannot be separated into evidence-bearing clusters versus philosophy or vibe
- there is not enough direct informal material to pressure Wave 04 claims honestly

## Anti-overclaim rules

- Do not let weak issue chatter upgrade confidence on its own.
- Do not collapse operator philosophy, issues, and postmortems into one evidence class.
- Do not use informal complaints as a substitute for source-backed state architecture.
- Do not smooth over disagreement between informal pressure and direct run behavior.

## Coverage reporting expectations

Your output must explicitly include:

- `coverage_used`
- `coverage_not_yet_used`
- `evidence_classes_touched`
- `priority_sources_not_yet_read`
- `support_artifacts_used`
- `support_artifacts_requested_or_deferred`
- `coverage_register_updates_needed`
- `required_dossier_updates`

## Wave 04 carry-forward cautions

Keep these visible in the output:

- BigAI remains `behavioral reconstruction`
- restart and resumability remain under-evidenced
- direct path accounting outranks organizer routing
- Wave 03 verifier/recovery tensions still matter when informal sources talk about stale state, restart, or cleanup

## Synthesis requirement

Do not stop at cluster lists or issue excerpts.

You must synthesize:

- which contradiction-pressure clusters matter for Wave 04
- which weak claims should be ignored or heavily caveated
- where informal pressure changes the mechanism picture
- what still cannot be defended from informal evidence
