# Preregistration and sentinels

This method writes the prediction, the falsifier, and the sentinel set down before any trial runs. A sentinel is a task that the change must not break. The record is kept in version control, so the prediction cannot move after the data arrives.

The lesson: a falsifier only counts if it can fire, and when it fires, the failed prediction is reported as failed.

This matters because most early wins in this programme appeared on one or two trials and did not survive a second look.

## Why we needed it

The only scored per-variant tournament in the repo was the one with a prediction written first. Its combined arm won 2 of 2 target rows but lost its one sentinel row. It was kept for follow-up and not promoted.

The tooling family rose to 7 of 7 with its guard, but a sentinel regressed. The same pattern appeared in every family where the guard raised target rows.

An N=1 win for the adaptive profile did not reproduce. In the reproducibility run the baseline passed 1 of 4 and the profile passed 3 of 4.

## How it works

Before the first trial, the change gets a prediction file, a stated falsifier, and named sentinel tasks. A change is kept only if it wins on target rows without regressing a sentinel. Failed predictions stay recorded as failed. The programme's own rule is that no variant runs without a target eval, a prediction, and named sentinels.

For the held-out evaluation, the design was sealed in version control before any row ran, and the stock reference's predicted range was written down before the run.

## What it caught

- **Guard arm with a sentinel loss.** The combined guard scored 2 of 2 on target rows and 0 of 1 on the sentinel. Total for the tournament was 6 of 12.
- **Falsifier fired on our own run.** The held-out evaluation predicted the stock reference would score 1 to 2 of 6. It scored 4 of 6. The candidate's predicted range for the long task also failed: all five long-task runs were still debugging at the 900-second limit. The falsifier triggered and the lift claim was not supported.

## Where it fell short

Sentinel sets are small. The first tournament had one sentinel. The rule that followed: a sentinel set at least as large as the target set. Preregistration also does not stop reinterpretation. One source reports the verifier-head holdout as 20 of 20 pooled, while another describes its verdict as positive on three controls. The two have not been reconciled.
