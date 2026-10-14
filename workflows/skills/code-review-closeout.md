# Code review closeout

Use this when a review is required to close a slice: non-trivial changes, policy or boundary changes, measurement-critical code, bug fixes a reviewer could plausibly disprove, or any slice whose review gate is part of its goal.

## Governing question

> Does the live diff actually do what the review says it does?

## Review path

Use the review helper if one is available: run it against the live diff and the evidence, capture findings with file and line context, then verify accepted findings with focused reruns.

If no helper is available, do the same by hand:

1. Read the live diff and the tests that should cover it, not only the summary.
2. Classify each finding as accepted, rejected, or needing more evidence.
3. For each rejection, give a concrete reason that holds against the live code: the path does not exist, the invariant is enforced elsewhere, the review misread the scope, or the behaviour is deliberately deferred and documented.
4. Fix accepted findings and rerun targeted checks.
5. Re-run the review lens on the updated diff.
6. Close only when residual risk is stated honestly.

## Disposition table

| Finding | Disposition | Evidence |
|---|---|---|
| (text, file, line) | accepted / rejected / needs_more_evidence | fix commit or rebuttal |

A finding is resolved only by a code or document change, or by an evidence rebuttal.

## Rerun expectations

Run the smallest check that would have caught each accepted finding: a focused test, a board row where relevant, a link check for docs, or a targeted reproduction. Then ask three questions: did the finding disappear, did the change add new risk, and does the remaining surface still match the review's claim?

## Review gate levels

| Gate | Use when |
|---|---|
| `none` | Formatting or wording with no contract attached |
| `adversarial_only` | A claim a reviewer could disprove, with a small diff |
| `review_skill` | Ordinary non-trivial code |
| `review_skill_plus_adversarial` | Measurement-critical, policy, or boundary code |

The gate is chosen before the work starts and recorded in the packet.

One broad review and one finding-focused re-review is the normal limit. Repeated structural findings mean redesign or block, not a third patch.

## Closeout

Include: the diff reviewed, findings and dispositions, accepted fixes with evidence, rejected findings with reasons, rerun commands and outputs, residual risk, and the next action. Use the [adversarial review closeout checklist](../templates/review-gate-checklist.md).
