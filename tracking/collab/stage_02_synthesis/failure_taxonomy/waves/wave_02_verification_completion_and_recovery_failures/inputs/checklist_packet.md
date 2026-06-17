# Failure Taxonomy Wave 02 Checklist Packet

Use this packet for primary GPT checklist adjudication in Wave 02.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_checklist_adjudicator_prompt.md`
3. this file

## Exact files to read

1. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/brief.md`
2. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/README.md`
3. `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
4. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
5. `tracking/collab/stage_02_synthesis/adjudication/DEEP_SYNTHESIS_V1_AUDIT_CHECKLIST.md`
6. `tracking/collab/stage_02_synthesis/adjudication/DEEP_SYNTHESIS_WAVE_AUDIT_CHECKLIST.md`
7. `tracking/collab/stage_02_synthesis/adjudication/FAILURE_TAXONOMY_AUDIT_CHECKLIST.md`
8. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
9. all Wave 02 lane outputs
10. Wave 02 contradiction output
11. Wave 02 principal synthesis

## Exact output path

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/adjudication/checklist_adjudicator.md`

## Exact Wave 02 attack surface

Audit whether the wave:

- solved verification/completion/recovery failure attribution
- kept symptom-vs-cause separation
- kept eval-lane evidence central as required
- avoided layer collapse and mixed-cause collapse

## Blocker vs carry-forward warning

`blocked`: acceptance would materially mislead downstream synthesis.

`pass_with_warnings`: useful wave with explicit unresolved uncertainty/debt.

`pass`: strong enough grounded attribution for governed carry-forward.

## Explicit distinction to enforce

- wave acceptance is not artifact completion
- checklist pass does not imply `failure_taxonomy` completion

## Explicit anti-collapse warning

Do not collapse model, harness, environment, and benchmark-contract causes when evidence is mixed.

## Dirty-worktree rule

- Expect unrelated dirty files and concurrent Deep Synthesis outputs.
- Do not stop for a dirty worktree alone.
- Edit only assigned Wave 02 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with assigned write scope.

