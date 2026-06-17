# Failure Taxonomy Wave 02 Model And Launch Recommendations

## Recommended models per lane

- trajectory/failure analyst: `GPT-5.4 xhigh`
- codebase/source reconstruction analyst: `GPT-5.3 Codex xhigh`
- literature/papers/docs analyst: `GPT-5.4 xhigh`
- informal/issues/postmortems analyst: `GPT-5.4 xhigh`
- eval/benchmark analyst: `GPT-5.4 xhigh`

## Support model recommendations

- bounded code-heavy support: `GPT-5.3 Codex high`
- bounded inventory/matrix/cluster support: `GPT-5.4-mini high`

## Gate model recommendations

- contradiction analyst: `GPT-5.4 xhigh`
- checklist adjudicator: `GPT-5.4 xhigh`
- Gemini gate: `Gemini 3.1 Pro` (breadth/long-context)
- Claude gate: `Claude Opus 4.6` (adversarial contradiction/acceptance)

## Eval policy for Wave 02

Eval is active as the fifth lane in this wave.

## Canonical output paths (from wave README)

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/trajectory_failure_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/codebase_source_reconstruction_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/literature_papers_docs_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_issues_postmortems_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/eval_benchmark_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/trajectory_support_false_completion_matrix.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/trajectory_support_recovery_failure_matrix.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/codebase_support_verifier_recovery_failure_map.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/codebase_support_completion_cleanup_map.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/literature_support_verification_recovery_failure_cluster.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_support_false_completion_recovery_cluster.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/eval_support_verifier_benchmark_contract_map.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/contradiction_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/contradiction_analyst__gemini.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/contradiction_analyst__claude.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/adjudication/checklist_adjudicator.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/adjudication/checklist_adjudicator__gemini.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/adjudication/checklist_adjudicator__claude.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/synthesis/principal_synthesis.md`

## Recommended launch order

1. trajectory lane
2. codebase/source lane
3. literature lane
4. informal lane
5. eval/benchmark lane
6. primary contradiction
7. optional Gemini/Claude contradiction gates
8. principal synthesis
9. primary checklist
10. optional Gemini/Claude checklist gates

## Dirty-worktree rule

- Expect unrelated dirty files and concurrent Deep Synthesis outputs.
- Do not stop for a dirty worktree alone.
- Edit only assigned Wave 02 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with assigned write scope.
