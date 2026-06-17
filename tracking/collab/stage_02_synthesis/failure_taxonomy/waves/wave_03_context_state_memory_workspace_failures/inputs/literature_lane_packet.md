# Failure Taxonomy Wave 03 Literature Lane Packet

Use this packet for the Wave 03 `literature/papers/docs analyst`.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_literature_papers_docs_analyst_prompt.md`
3. this file

## Exact role

- `literature/papers/docs analyst`

## Exact objective for Wave 03

Produce formal-source failure attribution for context/state/memory/workspace failures.

This is a failure-taxonomy wave, not a generic context/memory mechanism recap.

## Exact files to read first

1. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/brief.md`
2. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/support_subagent_rules.md`
3. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/README.md`
4. `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
5. `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
6. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
7. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_PHASE_AND_WAVE_OPERATING_PLAN.md`
8. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
9. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/adjudication/checklist_adjudicator.md`
10. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`

Then read:

- `research/sources/papers/papers_text/`
- `research/sources/docs/`

## Exact required dossier updates

- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/context_and_memory.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/workspace_and_artifact_discipline.md`
- `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/context_state_memory_workspace_failures.md`

## Exact output path

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/literature_papers_docs_analyst.md`

Follow-up outputs must use:

- `.../literature_papers_docs_analyst__followup_01.md`
- `.../literature_papers_docs_analyst__followup_02.md`
- `.../literature_papers_docs_analyst__revision_01.md`

## Exact support artifacts this lane may request

- `literature_support_context_memory_failure_cluster.md`

## Exact stop conditions

Stop and hand back if formal evidence cannot be mapped to attribution question without overriding stronger trajectory/source evidence.

## Exact anti-overclaim rules

- Do not turn mechanism vocabulary into failure proof.
- Do not collapse context/state/memory/workspace failure classes.
- Do not collapse model/harness/environment/benchmark-task-contract causes when mixed.

## Exact coverage reporting expectations

Include:

- `coverage_used`
- `coverage_not_yet_used`
- `support_artifacts_used`
- `support_artifacts_requested_or_deferred`
- `coverage_register_updates_needed`

## Dirty-worktree rule

- Expect unrelated dirty files and concurrent Deep Synthesis outputs.
- Do not stop for a dirty worktree alone.
- Edit only assigned Wave 03 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with the assigned write scope.

