# Case study 2: a pre-registered falsifier that fired

**Date:** 11 Oct 2026. **Rules that applied:** [governance rule 5](../governance.md#5-pre-registration-and-a-sealed-falsifier) (pre-registration) and [rule 6](../governance.md#6-invalid-row-accounting) (invalid-row accounting).

The team ran a held-out comparison between the harness and a stock reference agent on the same model. The falsifier for the claim was written before any result existed. The falsifier fired. The harness did not show the lift that the claim needed, and the record says so.

## What happened

The claim was that the harness lifts the model's pass rate on held-out tasks over a stock reference agent (Terminus-2) on the same model. Before the run, the pre-registration fixed the tasks, the scoring, the baseline, and the falsifier. The pre-registration was committed before the results commit, so the order is recoverable from version control.

## How the workflow caught it

The workflow did not let the verdict be written after the data. Three things held:

1. The pre-registration was sealed first.
2. The falsifier was stated in advance and recorded in the results commit subject.
3. The verdict was not softened. No "passed" claim was made.

An earlier 15 Sep audit had recorded a different held-out campaign at 0 of 3 official passes. That is a different campaign, so the two are not combined.

## Numbers

| Agent | Overall | Per task (three held-out tasks) |
|---|---|---|
| Harness | 5 of 9 | 3 of 3, 2 of 3, 0 of 3 |
| Stock reference agent (same model) | 4 of 6 | 2 of 2, 2 of 2, 0 of 2 |

The per-task split comes from the principal's working notes and was not re-checked against a repository. The overall counts are the recorded figures.

- Invalid rows: 0.
- One held-out task had a 900 s limit, against 1,800 s on a comparable task. Every run on that task was still mid-debug at the timeout. That is a confound, and it is recorded as one.
- The falsifier stated that the lift was not shown on these tasks.

## What changed

- The rule after this: any rerun is a new pre-registered campaign, compared against these numbers.
- Held-out material was closed to agents on 7 Oct, before the run. The principal controls when it is opened.
- Hosted-model runs were stopped on 11 Oct until further notice.

## What it does not show

Five of nine against four of six is a small sample. It does not show that the harness is worse than the stock agent in general. It shows that the lift claim was not supported on these three tasks, under this protocol.
