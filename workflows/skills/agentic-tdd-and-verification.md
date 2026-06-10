# Agentic TDD And Verification

## Governing Question

Can an agent change the system only after the acceptance surface is clear enough
to catch cheating, drift, and lucky passes?

This skill turns test-driven development into agent-driven development
discipline. The agent may implement quickly, but it must not define success
after seeing the implementation.

## When To Use

Use this skill for non-trivial code, eval, verifier, harness, or workflow
changes where correctness matters more than speed of the first patch.

Do not use it for mechanical documentation edits unless the docs encode a
contract, public claim, or evaluation rule.

## Workflow

1. State the behavior contract.
   - Name the user-visible or evaluator-visible behavior.
   - Name what is explicitly out of scope.
   - Identify the files, interfaces, or commands that define success.

2. Freeze the check before implementation.
   - Prefer an existing test, eval pack, verifier, or grader.
   - If no check exists, add the smallest deterministic one that expresses the
     intended behavior.
   - Include a known-bad path when feasible, especially for graders and
     validators.

3. Block easy cheating.
   - The implementation must not inspect hidden answers, task IDs, or evaluator
     internals.
   - The verifier must not accept mere claims when artifacts, commands, or file
     state are required.
   - The agent must not weaken tests to make the patch pass.

4. Implement the smallest coherent slice.
   - Keep write scope narrow.
   - Preserve unrelated dirty-tree changes.
   - Prefer existing project patterns over new abstractions.

5. Run target checks and sentinels.
   - Run the target test/eval first.
   - Run regression sentinels that cover adjacent failure modes.
   - Classify invalid environment/provider rows separately from capability
     failures.

6. Review the diff against the frozen contract.
   - If a test changed, explain why the changed test is stricter or more
     accurate.
   - Record accepted review findings and rejected findings with evidence.
   - Rerun focused checks after accepted fixes.

7. Close with a result row or handoff.
   - Include status, commands, outputs, files changed, residual risks, and the
     exact next action.

## Output Contract

A completed agentic TDD slice should leave:

- behavior contract;
- target test/eval/verifier path;
- known-bad or baseline evidence when feasible;
- implementation diff;
- target check result;
- sentinel result or reason omitted;
- review disposition;
- final status: `complete`, `partial`, `blocked`, or `invalid due to environment`.

Template: [Agentic TDD verification checklist](../templates/agentic-tdd-verification-checklist.md).

## Guardrails

- Traces diagnose; tests and evals decide.
- Passing once is not promotion if the row is invalid or contaminated.
- A changed test is suspicious until its stricter contract is explained.
- A verifier that accepts prose where artifacts are required is not a verifier.

## Sources

Derived from the repository's eval-first reset rules, the public
`eval_suite/` task-pack layout, the review-gate workflow in
[code-review-closeout](code-review-closeout.md), and the real implementation
handoff pattern captured in [loop-engineering/](../loop-engineering/).
