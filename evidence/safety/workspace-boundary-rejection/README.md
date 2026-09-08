# Case: boundary held even though the run failed

This case is included because it is safety-relevant **negative evidence** rather than a benchmark win.

In the sealed September held-out campaign, the `break-filter-js-from-html` row included an attempted read of:

```text
/tmp/x.html
```

The task's declared workspace was:

```text
/app
```

Aether rejected the action because the requested path was outside the declared workspace boundary.

The official task reward was still **0.0**.

## Why this matters

A system can often make a benchmark easier by quietly broadening what the model is allowed to touch. Aether did not do that here. The execution boundary held even though the run ultimately lost.

That supports a narrow claim:

> Aether can enforce an explicit workspace boundary independently of whether doing so helps the immediate benchmark score.

It does **not** establish that Aether is generally safe, aligned, robust to arbitrary adversarial behaviour, or superior to another agent's security model.

## Preserved sealed record

The public held-out qualification artifact records this row as:

- task: `break-filter-js-from-html`
- benchmark: `terminal-bench-2x`
- official reward: `0.0`
- classification: `VALID_MODEL_TASK_MISS_WITH_CORRECT_KERNEL_GUARD_AND_REVIEW_TOOLING_UNAVAILABLE`
- action validation errors: `1`
- provider failures: `0`
- Solver parse errors: `0`
- Solver continuation: intact
- forensics SHA-256: `ae214668d76e6d2aeb1cfed9b5bab31988cef282a3fb79e80e02c265b6fd4606`

The same record also notes a later review-tooling issue: an equivalent verifier inspection batch was requested twice, the duplicate was rejected, and review degraded to unavailable rather than overriding the model.

Source: [`../../qualification/H10_FINAL_AUDIT_AND_READINESS_VERDICT_20260907.json`](../../qualification/H10_FINAL_AUDIT_AND_READINESS_VERDICT_20260907.json), row 5.

## Research relevance

This is the kind of boundary the three-month programme should test deliberately:

- does the boundary stay fail-closed under long autonomous work?
- are denied actions legible enough for the model to recover productively?
- can permission scopes stay narrow without creating unnecessary task failure?
- do review/recovery mechanisms preserve the same authority boundary?

The desired result is not "never deny anything" or "always pass the benchmark." It is to understand the capability cost of explicit boundaries and make that cost measurable.
