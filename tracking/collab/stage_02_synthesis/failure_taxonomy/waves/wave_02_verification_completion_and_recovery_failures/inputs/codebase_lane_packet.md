# Failure Taxonomy Wave 02 Codebase Lane Packet

Use this packet for the Wave 02 `codebase/source-reconstruction analyst`.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_codebase_source_reconstruction_analyst_prompt.md`
3. this file

## Exact role

- `codebase/source-reconstruction analyst`

## Exact objective for Wave 02

Produce source-grounded failure attribution for verifier, completion, cleanup, replay, and recovery failures.

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

- `research/sources/codebases/deepagents/`
- `research/sources/codebases/KIRA/`
- `research/sources/codebases/a-evolve/`
- `blocks/`
- `runner/`
- `evals/`

## Exact required dossier updates

- `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/verification_and_replay.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/checkpoint_restore_and_resumability.md`
- `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/verification_completion_recovery_failures.md`
- `tracking/collab/stage_02_synthesis/eval_benchmark_dossiers/verification_completion_and_recovery.md`
- `tracking/collab/stage_02_synthesis/eval_benchmark_dossiers/verification_completion_recovery_failures.md`

## Exact required case-study updates where relevant

- `tracking/collab/stage_02_synthesis/trajectory_case_studies/db_wal_recovery.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md`
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`

## Exact output path

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/codebase_source_reconstruction_analyst.md`

Follow-up outputs must use:

- `.../codebase_source_reconstruction_analyst__followup_01.md`
- `.../codebase_source_reconstruction_analyst__followup_02.md`
- `.../codebase_source_reconstruction_analyst__revision_01.md`

## Exact support artifacts this lane may request

- `codebase_support_verifier_recovery_failure_map.md`
- `codebase_support_completion_cleanup_map.md`

## Exact stop conditions

Stop and hand back if:

- source visibility is too thin for cross-family attribution
- trajectory-source linkage cannot be established for major claims

## Exact anti-overclaim rules

- Keep BigAI out of source-backed claims.
- Do not collapse verification/replay/grading/acceptance/cleanup layers.
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

