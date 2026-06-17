# Wave 04 Codebase Lane Packet

Use this packet for the Wave 04 `codebase/source-reconstruction analyst`.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_codebase_source_reconstruction_analyst_prompt.md`
3. this file

## Exact role

- `codebase/source-reconstruction analyst`

## Exact Wave 04 objective

Produce the implementation-grounded Wave 04 synthesis for `context_state_memory_workspace`.

You must explain, from visible source first:

- where context is assembled, compacted, summarized, or restored
- where state is persisted, replayed, resumed, or reset
- where memory is written, retrieved, scoped, or allowed to drift stale
- how workspace artifacts, branches, sessions, and files act as the real state substrate
- how first-class systems differ from archive-only or exploratory source pressure

This is a synthesis task, not a code index.

## Read these files first

1. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/brief.md`
2. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/inputs/support_subagent_rules.md`
3. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
4. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
5. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
6. `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
7. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
8. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`

## Required direct source paths

You must read directly from these path families unless blocked:

- `research/sources/codebases/deepagents/`
- `research/sources/codebases/KIRA/`
- `research/sources/codebases/a-evolve/`
- `research/sources/codebases/quarantine/claw-code/`
- `blocks/`
- `runner/`
- `evals/`

Priority themes to trace:

- context assembly
- state persistence
- session state
- memory stores and retrieval
- compaction and summarization
- workspace and artifact discipline
- branch/worktree safety
- reset, resume, and stale-state prevention

## Required dossier updates to inform or request

- `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`

## Required case-study updates where relevant

- `tracking/collab/stage_02_synthesis/trajectory_case_studies/git_multibranch.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/break_filter_js_from_html.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/custom_memory_heap_crash.md`

## Output path

Write exactly here:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_source_reconstruction_analyst.md`

If you need a follow-up, do not overwrite. Use:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_source_reconstruction_analyst__followup_01.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_source_reconstruction_analyst__followup_02.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_source_reconstruction_analyst__revision_01.md`

## Support artifacts you may request

You may request bounded support artifacts such as:

- `codebase_support_context_state_map.md`
- `codebase_support_workspace_artifact_map.md`
- `codebase_support_compaction_handoff_map.md`
- `codebase_support_claw_code_runtime_state_map.md`

Support artifacts must be explicit files under:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/`

## Stop conditions

Stop and return control to the principal if any of these are true:

- visible source is too thin to distinguish context, memory, and workspace mechanisms honestly
- archive or quarantine captures would be doing most of the work for promoted claims
- the lane would need to treat speculative route maps as source-backed implementation
- eval would need to be reactivated to explain the core mechanism judgment

## Anti-overclaim rules

- Do not treat archive-only `src_cod_*` style pressure as first-class implementation proof.
- Do not treat `claw-code` quarantine material as equal to first-class mirrored systems without saying so.
- Do not collapse context compaction, memory persistence, and workspace artifact discipline into one mechanism family without direct source support.
- Do not claim restart-safe resumability is established from source alone.
- Do not use BigAI as source-backed implementation.

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
- restart and resumability remain under-evidenced at the behavior layer
- direct path accounting outranks organizer routing while organizer remains empty
- Wave 03 verifier/recovery families are real but do not automatically settle context/state/workspace architecture

## Synthesis requirement

Do not stop at file lists or subsystem notes.

You must synthesize:

- which implementation families are genuinely visible
- which state substrates are explicit versus inferred
- what simple workspace-artifact baselines compete with richer memory systems
- where source and trajectory appear aligned versus in tension
