# Failure Taxonomy Wave 03 Eval Reactivation Packet

Wave 03 keeps eval/benchmark inactive by default.

Reactivate eval only if one or more become load-bearing for attribution:

- benchmark state contracts
- replay state expectations
- grader workspace expectations
- task persistence contracts

If reactivated, use:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_eval_benchmark_analyst_prompt.md`
3. this file

Reactivated eval output path:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/eval_benchmark_analyst.md`

Recommended support artifact if reactivated:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/eval_support_state_contract_map.md`

Reactivation guardrails:

- Do not open eval for generic breadth.
- Use eval only when it changes causal attribution quality.
- Keep context/state/memory/workspace attribution primary.

## Dirty-worktree rule

- Expect unrelated dirty files and concurrent Deep Synthesis outputs.
- Do not stop for a dirty worktree alone.
- Edit only assigned Wave 03 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with the assigned write scope.

