# Failure Taxonomy Wave 04 Contradiction Packet

Use this packet for primary contradiction review in Wave 04.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_contradiction_analyst_prompt.md`
3. this file

## Exact files to read

1. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/brief.md`
2. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/README.md`
3. `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
4. `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
5. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
6. all first-pass Wave 04 lane outputs
7. cited support outputs

## Exact output path

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/contradiction_analyst.md`

## Exact Wave 04 attack surface

Attack:

- collapse of tool/environment/coordination/timeout failure classes into one bucket
- unsupported over-claims without path-backed attribution
- removal of terminal-first/single-agent baseline comparisons
- BigAI promoted beyond behavioral constraints
- mixed-cause uncertainty hidden by single-cause claims

## Blocker vs carry-forward warning

`blocked`: structural attribution collapse or unsupported promoted claims.

`pass_with_warnings`: useful synthesis with explicit unresolved uncertainty.

`pass`: grounded attribution with bounded uncertainty.

## Explicit distinctions

- wave acceptance is not artifact completion
- no family becomes `decision_ready` by wave pass alone
- do not collapse model/harness/environment/benchmark-pressure causes when mixed

## Dirty-worktree rule

- Expect unrelated dirty files and concurrent Deep Synthesis outputs.
- Do not stop for a dirty worktree alone.
- Edit only assigned Wave 04 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with assigned write scope.

