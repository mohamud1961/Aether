# Wave 04 Trajectory Lane Packet

Use this packet for the Wave 04 `trajectory/failure analyst`.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_trajectory_failure_analyst_prompt.md`
3. this file

## Exact role

- `trajectory/failure analyst`

## Exact Wave 04 objective

Produce the behavior-anchored Wave 04 synthesis for `context_state_memory_workspace`.

You must explain, from direct runs first:

- what context is actively retained, compressed, discarded, or reintroduced
- how state persists or drifts across turns and task phases
- how memory is written, retrieved, ignored, or goes stale
- how workspace and artifact discipline shape state continuity
- how branch/worktree hygiene interacts with state safety
- where BigAI can only be discussed as `behavioral reconstruction`

This is a synthesis task, not an inventory-only pass.

## Read these files first

1. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/brief.md`
2. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/inputs/support_subagent_rules.md`
3. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
4. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
5. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
6. `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
7. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
8. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`

## Required direct evidence paths

You must read directly from these path families unless blocked:

- `research/sources/trajectories/BigAI/git-multibranch/`
- `research/sources/trajectories/deepagents/git-multibranch/`
- `research/sources/trajectories/terminus-kira/git-multibranch/`
- `research/sources/trajectories/BigAI/break-filter-js-from-html/`
- `research/sources/trajectories/deepagents/break-filter-js-from-html/`
- `research/sources/trajectories/terminus-kira/break-filter-js-from-html/`
- `research/sources/trajectories/BigAI/custom-memory-heap-crash/`
- `research/sources/trajectories/deepagents/custom-memory-heap-crash/`
- `research/sources/trajectories/terminus-kira/custom-memory-heap-crash/`

Pressure-test paths when time permits:

- `research/sources/trajectories/*/headless-terminal/`
- `research/sources/trajectories/*/large-scale-text-editing/`

## Required dossier updates to inform or request

- `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`

## Required case-study updates

- `tracking/collab/stage_02_synthesis/trajectory_case_studies/git_multibranch.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/break_filter_js_from_html.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/custom_memory_heap_crash.md`

## Output path

Write exactly here:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_failure_analyst.md`

If you need a follow-up, do not overwrite. Use:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_failure_analyst__followup_01.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_failure_analyst__followup_02.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_failure_analyst__revision_01.md`

## Support artifacts you may request

You may request bounded support artifacts such as:

- `trajectory_support_context_workspace_matrix.md`
- `trajectory_support_memory_state_drift_cases.md`
- `trajectory_support_branch_worktree_state_table.md`
- `trajectory_support_run_to_source_link_map.md`

Support artifacts must be explicit files under:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/`

## Stop conditions

Stop and return control to the principal if any of these are true:

- the Wave 04 domain cannot be addressed without silently reactivating eval
- the direct trajectory slice coverage is too thin to support honest cross-family claims
- you cannot separate observation from inference for the promoted families
- the wave would collapse into generic “memory is important” rhetoric instead of domain-specific mechanism synthesis

## Anti-overclaim rules

- Do not treat BigAI as source-backed. Keep it `behavioral reconstruction`.
- Do not promote restart or restart-safe resumability beyond `exploratory`.
- Do not let the empty organizer file substitute for direct path accounting.
- Do not treat a run as evidence of durable memory architecture if it only shows workspace artifact continuity.
- Do not confuse branch hygiene, worktree safety, and long-term memory.
- Do not claim full trajectory coverage unless you enumerate concrete paths read.

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
- organizer routing is still weaker than direct path accounting
- Wave 03 completion and recovery findings remain real, but they do not settle context/state/workspace families automatically

## Synthesis requirement

Do not stop at note collection, case summaries, or matrices.

You must synthesize:

- candidate mechanism families
- the minimal-sufficient baselines that compete with richer memory claims
- the strongest cross-run similarities and divergences
- what remains unresolved even after the read
