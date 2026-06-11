# Review Repair Loop

Use this skill when findings from a review thread, code review helper, or
adversarial pass must be turned into a corrected diff.

The goal is not to "address comments" cosmetically. The goal is to preserve
the reviewer signal, apply accepted fixes, reject only with evidence, and
rerun the checks that matter.

## Governing Question

Which findings are real, which fixes were applied, and which evidence proves
the corrected slice is now safer?

## Use Cases

- Repair a code diff after an independent review thread.
- Repair a public-claim document after provenance review.
- Resolve failed validation from a tournament or run-analysis closeout.
- Re-run a review gate after accepted findings were fixed.

## Workflow

1. **Ingest findings**
   - Preserve finding text, severity, file/path, and evidence.
   - Group duplicates without dropping material claims.

2. **Classify**
   - `accept`: true and in scope.
   - `reject`: false, already handled, or contradicted by evidence.
   - `defer`: true but outside current scope.
   - `block`: cannot decide without missing dependency.

3. **Patch accepted findings**
   - Apply only accepted in-scope fixes.
   - Keep fixes narrow and reviewable.

4. **Rerun focused checks**
   - Run the check that would have caught the finding.
   - Run adjacent sentinels if the fix touches shared behavior.

5. **Second-pass review**
   - Re-review the changed area.
   - Do not let new unrelated refactors enter the repair loop.

6. **Closeout**
   - Report every finding disposition and residual risk.

## Output Contract

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

- Do not mark a finding resolved without a code/doc change or evidence rebuttal.
- Do not bundle unrelated cleanup into a review repair patch.
- Do not rerun only the easy check if the finding concerns a harder surface.
- Stop after repeated unclear findings and escalate to the orchestrator.

