# Failure Taxonomy Wave 02 Contradiction Packet

Use this packet for primary contradiction review in Wave 02.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_contradiction_analyst_prompt.md`
3. this file

## Exact files to read

Read first:

1. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/brief.md`
2. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/README.md`
3. `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
4. `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
5. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
6. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/adjudication/checklist_adjudicator.md`
7. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`

Then read all first-pass lane outputs:

- `.../outputs/trajectory_failure_analyst.md`
- `.../outputs/codebase_source_reconstruction_analyst.md`
- `.../outputs/literature_papers_docs_analyst.md`
- `.../outputs/informal_issues_postmortems_analyst.md`
- `.../outputs/eval_benchmark_analyst.md`

and any materially cited support artifacts.

## Exact output path

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/contradiction_analyst.md`

## Exact Wave 02 attack surface

Attack:

- false completion claims not tied to verifier/benchmark/replay evidence
- over-attribution to one cause family when evidence is mixed
- hidden collapse of inline proof, verifier, grader, replay, acceptance, cleanup
- benchmark-contract blindness undercounting
- BigAI promoted beyond behavioral bounds
- support artifacts treated as final claims

## Blocker vs carry-forward warning

`blocked`:

- core attribution is structurally unsupported or collapsed

`pass_with_warnings`:

- useful wave output with explicit unresolved mixed-cause uncertainty

`pass`:

- attribution is well-grounded and uncertainty is explicitly bounded

## Explicit distinction to enforce

- wave acceptance is not artifact completion
- accepted Wave 02 can still leave `failure_taxonomy` incomplete

## Explicit anti-collapse warning

Do not collapse model, harness, environment, and benchmark-contract causes when evidence is mixed.

## Dirty-worktree rule

- Expect unrelated dirty files and concurrent Deep Synthesis outputs.
- Do not stop for a dirty worktree alone.
- Edit only assigned Wave 02 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with assigned write scope.

