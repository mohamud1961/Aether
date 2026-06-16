# Adversarial Code Review Closeout Checklist

Use this when a review or red-team pass needs a precise closeout.

## Inputs

- the actual diff or changed files;
- review findings or comments;
- validation commands and outputs;
- any known residual risks.

## Checklist

- Re-read the live diff, not just the summary.
- Classify each finding as accepted, rejected, or needing more evidence.
- If accepted, make the fix and rerun focused validation.
- If rejected, explain why the finding does not hold against the live code.
- Check that the fix did not introduce a new regression or overclaim.
- State the residual risk honestly.
- Name the next concrete action if the slice should stay open.

## Closeout Output

- findings table;
- accepted fixes and evidence;
- rejected findings and reason;
- residual risks;
- next action.

