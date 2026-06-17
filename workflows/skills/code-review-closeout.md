# Code Review Closeout

Use this skill when code review is required to close a slice.

This is part of the Loop Engineering family. It turns a review into a decision
process: what the diff actually does, which findings are real, what was fixed,
and what evidence closes the loop.

## Governing Question

> Does the live diff actually do what the review says it does?

## When To Use

Use this skill for:

- non-trivial code changes;
- policy or boundary changes;
- eval substrate or measurement-critical changes;
- bug fixes where a reviewer could plausibly disprove the closeout;
- slices where the review gate is part of the goal contract.

## Preferred Review Path

If the local `codex-review` skill or helper is available, use it first.

That means:

1. restore or re-open the helper according to the local review workflow;
2. run the review against the live diff and evidence;
3. capture findings with file and line context;
4. verify accepted findings with focused reruns.

If the helper is unavailable, fall back to manual adversarial review.

## Manual Review Path

When the helper is unavailable, do the same work explicitly:

1. read the live diff and the tests that should cover it;
2. classify each finding as accepted, rejected, or needing more evidence;
3. record why rejected findings do not hold against the live code;
4. fix accepted findings and rerun targeted validation;
5. re-run the review lens against the updated diff;
6. close only when residual risk is honestly stated.

## Finding Disposition

Use a simple disposition table:

- `accepted`: the finding is real and the slice must change;
- `rejected`: the finding does not hold against the live code;
- `needs_more_evidence`: the finding may be real, but the current evidence is
  insufficient.

Good rejection reasons are concrete:

- the path does not exist;
- the invariant is already enforced elsewhere;
- the review misread the scope;
- the behavior is intentionally deferred and documented.

## Rerun Expectations

If a finding is accepted, rerun the smallest useful checks that prove the fix:

- unit or smoke tests;
- board or scoreboard rows when relevant;
- path or link checks for docs slices;
- diff checks for formatting or structure;
- targeted reproduction of the reported issue.

Then re-run the review lens:

- did the accepted finding disappear?
- did the change introduce a new risk?
- does the remaining surface still match the review claim?

## Handoff Evidence

The closeout handoff should include:

- the diff under review;
- review findings and dispositions;
- accepted fixes and evidence;
- consciously rejected findings and why;
- rerun commands and outputs;
- residual risk;
- the next concrete action.

Use the companion checklist for the compact form:

[Adversarial code review closeout checklist](../templates/adversarial-code-review-closeout-checklist.md)

