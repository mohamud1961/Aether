# Eval-First Implementation Slice

Use this before implementing a non-trivial harness change.

## Before Coding

- Name the failure family or capability gap.
- Define the target eval or diagnostic.
- Record the predicted score or behavior change.
- Name regression sentinels.
- Confirm what counts as baseline, ceiling, and known-bad.
- Confirm the slice is generic, not suite-specific.

## During The Slice

- Keep the implementation bounded to one mechanism change.
- Preserve exact evidence paths for tests, boards, and score rows.
- Record simplifications and intentionally deferred behavior.
- Avoid silent objective changes if the prediction fails.

## Exit Criteria

- target eval rerun completed;
- sentinels rerun completed;
- keep, kill, or iterate decision written down;
- residual risks and blocked dependencies named explicitly.
