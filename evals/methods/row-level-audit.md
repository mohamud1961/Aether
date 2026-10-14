# Row-level audit

This method reads every scored trial and checks that the score matches the work. Each trial gets a classification. Harness defects and grader defects are logged with the trial's ID before any aggregate is used.

The lesson: aggregates hid defects that reading the rows found in one pass. This is the strongest evidence the programme has.

This matters because a plausible score can sit on top of wrong rows, and the aggregate will not show it.

## Why we needed it

The development sweep on 29 unique Terminal-Bench 2.1 tasks changed code between rows. Every row was audited. The audit found 11 harness defects, and they were fixed. Three rows were killed by a harness defect and then failed on domain grounds. The best attempt was 18 of 29, and the first valid attempt was 17 of 29. The sweep is a development record, not a fixed comparison.

## How it works

For each trial the audit runs in order:

1. Confirm the launch and check that the trial is valid.
2. Read the trace for the decision that set the score.
3. Compare the grader outcome with the trace.
4. Classify the result as a capability failure, an environment failure, a harness defect, or a grader defect. Environment and capability failures are kept apart.
5. Log each defect with its trial ID. Only valid trials enter the score.

Failed predictions are recorded as failed and are not reinterpreted as wins.

## What it caught

- **Wrong default setting.** A row audit found that the open-model runs used temperature 0.0 by default.
- **Path-base effect.** The first file read failed in every control and succeeded in every treatment. Only reading the rows showed the cause.
- **Task defects.** About 18 of 60 trials were always 0 across arms. The cause was in the task cards, not the candidate.
- **Inert arm.** An arm with no verifier callback made zero broker requests. Row reading showed it.
- **Non-capability losses.** Two candidate losses traced to card defects, fixed in a later version. Two control losses were timeouts.

## Where it fell short

The audit is manual reading of traces. It does not scale to the 241-trial board, and no inter-reviewer check is recorded. The audit only sees what the trace shows, so it can miss defects that leave no trace. The development sweep's 18 of 29 figure is cited from a document that is not in the repo, and the sweep is not comparable to the held-out results.
