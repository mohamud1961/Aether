# Eval-Driven Development

## Purpose

Use this workflow when a coding agent is about to implement or modify behavior.
The check must exist before the agent can claim success.

## Loop

1. State the behavior in a bounded contract.
2. Create or select the smallest useful eval, smoke pack, unit test, or
   sentinel.
3. Run a baseline or known-bad check when feasible.
4. Implement the smallest slice.
5. Run the target check and regression sentinels.
6. Review the diff with a maker/checker split.
7. Promote, kill, or rerun based on evidence.

## Evidence Artifacts

- Target eval or test path.
- Baseline or known-bad result when feasible.
- Result row, scoreboard, or validation command output.
- Review disposition: accepted fixes, rejected findings, and unresolved risks.
- Final decision: promote, kill, rerun, or follow-up.

## Public Examples

- `eval_suite/families/environment/runtime_policy_hook_smoke/`
- `eval_suite/families/tooling/mcp_registry_contract_smoke/`
- `eval_suite/families/tooling/skill_loader_contract_smoke/`
- `eval_suite/families/orchestration/subagent_handoff_contract_smoke/`
- `docs/case-studies/aether-runtime-capability-migration.md`

## Skills

- `../skills/agentic-tdd-and-verification.md`
- `../skills/eval-first-implementation-slice.md`
- `../skills/implementation-loop.md`
- `../skills/review-repair-loop.md`
- `../skills/tournament-runner.md`

## Anti-Cheating Rules

- The implementation agent cannot define success after the fact.
- Local proxy checks do not override the frozen eval contract.
- Passing the target check is not enough if a named sentinel regresses.
- Invalid environment rows must be classified before capability conclusions.
- Scoreboards beat narrative summaries.
