# Failure Taxonomy Wave 02 Informal Lane Packet

Use this packet for the Wave 02 `informal/issues/postmortems analyst`.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_informal_issues_postmortems_analyst_prompt.md`
3. this file

## Exact role

- `informal/issues/postmortems analyst`

## Exact objective for Wave 02

Produce contradiction-pressure failure attribution for verification/completion/recovery failures.

This is a failure-taxonomy wave, not a generic verification recap.

## Exact files to read first

1. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/brief.md`
2. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/inputs/support_subagent_rules.md`
3. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/README.md`
4. `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
5. `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
6. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
7. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_PHASE_AND_WAVE_OPERATING_PLAN.md`
8. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
9. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/adjudication/checklist_adjudicator.md`
10. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`

Then read:

- `research/sources/informal/`
- `research/sources/issues/`
- `research/sources/postmortems/`

## Exact required dossier updates

- `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/verification_completion_recovery_failures.md`
- `tracking/collab/stage_02_synthesis/eval_benchmark_dossiers/verification_completion_recovery_failures.md`

## Exact output path

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_issues_postmortems_analyst.md`

Follow-up outputs must use:

- `.../informal_issues_postmortems_analyst__followup_01.md`
- `.../informal_issues_postmortems_analyst__followup_02.md`
- `.../informal_issues_postmortems_analyst__revision_01.md`

## Exact support artifacts this lane may request

- `informal_support_false_completion_recovery_cluster.md`

## Exact stop conditions

Stop and hand back if:

- coverage is too sparse for credible contradiction pressure
- mixed-cause attribution cannot be preserved

## Exact anti-overclaim rules

- Do not treat issue chatter as source-backed proof.
- Do not collapse verification/completion/recovery layers.
- Do not collapse model/harness/environment/benchmark-contract causes when mixed.

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
- Edit only assigned Wave 02 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with assigned write scope.

