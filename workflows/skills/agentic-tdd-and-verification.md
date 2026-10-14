# Agentic TDD and verification

Use this for non-trivial code, eval, verifier, or workflow changes where correctness matters more than speed of the first patch. Do not use it for mechanical documentation unless the document encodes a contract or public claim.

The agent may implement quickly. It must not define success after seeing its own implementation.

## Governing question

> Can the agent change the system only after the acceptance surface is clear enough to catch cheating, drift, and lucky passes?

## Workflow

1. **State the behaviour contract.** Name the behaviour the user or evaluator sees, what is out of scope, and which files, interfaces, or commands define success.
2. **Freeze the check before implementing.** Prefer an existing test, eval, verifier, or grader. If none exists, add the smallest deterministic one. Include a known-bad case where possible, especially for graders and validators.
3. **Block easy cheating.** The implementation must not read hidden answers, task identifiers, or evaluator internals. The verifier must require artifacts or state when a claim is not enough. The agent must not weaken a test to pass.
4. **Implement the smallest coherent slice.** Keep write scope narrow. Preserve unrelated changes in the tree. Prefer existing patterns over new abstractions.
5. **Run the target check, then the sentinels.** Sentinels cover adjacent failure modes. Classify invalid environment or provider rows separately from capability failures.
6. **Review the diff against the fixed contract.** If a test changed, explain why the change is stricter or more accurate. Record accepted and rejected findings with evidence. Rerun focused checks after accepted fixes.
7. **Close with a result row or handoff.** Include status, commands, outputs, files changed, residual risks, and the next action.

## Output

- behaviour contract;
- target check path;
- known-bad or baseline evidence where feasible;
- implementation diff;
- target result;
- sentinel result, or the reason it was omitted;
- review dispositions;
- final status: complete, partial, blocked, or invalid due to environment.

Template: [pre-registration](../templates/pre-registration.md). Fill its checks-fixed section before implementing.

## Guardrails

- Traces diagnose. Tests and evals decide.
- A pass on one run is not promotion if the row is invalid or contaminated.
- A changed test is suspicious until its stricter contract is explained.
- A verifier that accepts prose where artifacts are required is not a verifier.
