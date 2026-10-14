# Review gate closeout checklist

Use this to close a slice that has passed through a review gate: a review helper, an adversarial pass, or a manual review.

## Inputs

- The actual diff or changed files, read live.
- Review findings or comments, with location.
- Validation commands and their outputs.
- Known residual risks.
- The gate level chosen before the work: `none`, `adversarial_only`, `review_skill`, or `review_skill_plus_adversarial`.

## Checklist

- [ ] Re-read the live diff, not only the summary.
- [ ] Each finding is classed accepted, rejected, or needs_more_evidence.
- [ ] Each accepted finding has a code or document change and a focused rerun.
- [ ] Each rejected finding has a concrete reason that holds against the live code.
- [ ] The fix did not add a regression or an overclaim.
- [ ] Re-review of the changed area is done. If it is the second round and the same structural finding returned, the slice goes to redesign, not a third patch.
- [ ] Residual risk is stated.
- [ ] If the slice stays open, the next action is named.

## Disposition table

| # | Finding (file, line) | Disposition | Evidence (fix or rebuttal) | Rerun command and result |
|---|---|---|---|---|
| 1 | | accepted / rejected / needs_more_evidence | | |

## Closeout

- Gate level used:
- Accepted fixes and evidence:
- Rejected findings and reasons:
- Residual risk:
- Final status: complete | partial | blocked | invalid_due_to_environment
- Next action:
