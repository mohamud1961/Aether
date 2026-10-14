# Review repair loop

Use this when findings from a review, a review helper, or an adversarial pass must become a corrected diff.

The goal is not to address comments cosmetically. Keep the reviewer's signal, apply accepted fixes, reject only with evidence, and rerun the checks that matter.

## Governing question

> Which findings are real, which fixes were applied, and which evidence shows the corrected slice is safer?

## Workflow

1. **Ingest.** Keep each finding's text, severity, location, and evidence. Group duplicates without dropping any material claim.
2. **Classify.**
   - `accept`: true and in scope.
   - `reject`: false, already handled, or contradicted by evidence.
   - `defer`: true but outside this slice.
   - `block`: cannot be decided without a missing dependency.
3. **Patch accepted findings only.** Keep each fix narrow and reviewable.
4. **Rerun the check that would have caught the finding.** If the fix touches shared behaviour, also run adjacent sentinels. Do not run only the easy check when the finding concerns a harder surface.
5. **Second-pass review** of the changed area. Do not let unrelated refactors into the repair.
6. **Closeout.** Report every disposition and the residual risk.

## Output

```text
review_source:
findings:
accepted:
rejected:
deferred:
blocked:
files_changed:
checks_run:
second_pass_result:
residual_risk:
next_action:
```

## Guardrails

- Do not mark a finding resolved without a code or document change, or an evidence rebuttal.
- Do not bundle unrelated cleanup into a repair patch.
- Stop after repeated unclear findings and escalate to the orchestrator.
- Two review rounds is the normal limit. If the same structural finding returns, redesign instead of patching again.
