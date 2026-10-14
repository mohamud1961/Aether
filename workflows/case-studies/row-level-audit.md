# Case study 3: a row-level audit that kept the invalid row

**Dates:** 30 Aug 2026 (one task row) and 30 Sep 2026 (repair closed at row 51). **Rules that applied:** [governance rule 6](../governance.md#6-invalid-row-accounting) (invalid-row accounting) and [rule 7](../governance.md#7-no-blind-retries-run-freeze) (no blind retries).

This episode is about the bookkeeping of single rows. A row can look like a failure or a success for reasons that have nothing to do with the model. The workflow's rule is to classify the row, keep it, and count it on its own terms.

## Part A: one invalid task row (30 Aug)

An official grader scored one row at 0.0. The paid attempt for that row lacked cost telemetry, so the row was treated as an invalid measurement.

A blind retry would have replaced the row. The rule forbids that. The row was logged as a consumed invalid measurement. Its forensics reconstructed all five official trajectories and 62 provider attempts for that task.

The next run was launched on 31 Aug. An adversarial review of its launch bundle the same day found static identity problems in the bundle.

## Part B: a closed repair at row 51 (30 Sep)

A repair run for one comparison was stopped at ordinal 51, where a row was invalid. The run was closed as an incomplete discovery screen, not finished. The 50 valid rows were kept. The invalid row was not replaced.

| Outcome for the 25 matched pairs | Count |
|---|---|
| Both pass | 11 |
| Both fail | 10 |
| Treatment only pass | 3 |
| Control only pass | 1 |

The result was reported as a screen with 25 matched pairs. It was not reported as a finished comparison.

## What the workflow did differently

- Each invalid row was classed by cause (provider, protocol, environment, grader, or model) before any capability claim.
- Invalid rows stayed in the record and were excluded from the capability denominator.
- Retries were not used to fill a gap. A campaign with an invalid slot is non-qualifying under the protocol.
- The closure was recorded as incomplete, with the reason.

## Numbers

- Invalid row: 0.0 on the official grader, 5 official trajectories, 62 provider attempts.
- Repair: stopped at row 51, 50 valid rows, 25 matched pairs.

## What it does not show

The pairs are a small screen. The 11 and 10 counts are agreement, not a verdict on either arm. The two sides are not compared as a win on these numbers.
