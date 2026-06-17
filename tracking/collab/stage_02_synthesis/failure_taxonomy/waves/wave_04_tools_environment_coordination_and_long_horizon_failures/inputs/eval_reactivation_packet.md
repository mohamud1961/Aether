# Failure Taxonomy Wave 04 Eval Reactivation Packet

Wave 04 keeps eval/benchmark inactive by default.

Reactivate eval only if one or more become load-bearing:

- benchmark time budgets
- grader/tool contracts
- replay requirements
- benchmark workspace assumptions

If reactivated, use:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_eval_benchmark_analyst_prompt.md`
3. this file

Reactivated eval output path:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/eval_benchmark_analyst.md`

Recommended support artifact if reactivated:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/eval_support_benchmark_time_contract_map.md`

Reactivation guardrails:

- Do not open eval for generic breadth.
- Use eval only when it changes causal attribution quality.
- Keep tool/environment/coordination failure attribution primary.

## Dirty-worktree rule

- Expect unrelated dirty files and concurrent Deep Synthesis outputs.
- Do not stop for a dirty worktree alone.
- Edit only assigned Wave 04 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with assigned write scope.

