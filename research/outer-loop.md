# The outer loop: from trajectories to harness changes

The programme ran one loop again and again: read trajectories, name the failure, build an evaluation
that catches it, change the harness, and measure whether the evaluation moves. This page shows four
real turns of that loop. The pattern matters more than any single result.

```
 trajectories ──► failure named ──► eval that catches it ──► harness change ──► measured again
      ▲                                                                              │
      └──────────────────────────── new trajectories ◄──────────────────────────────┘
```

## Turn 1: the verifier that did not verify

| Step | What happened |
|---|---|
| Trajectories | Audits found the verifier had run 0 real checks across 20 runs, and sentinel runs showed false cleans (2 of 5, then 1 of 2) |
| Eval | A known-bad falsifier: frozen wrong and right end states replayed through one verifier round. It never passed (3/5, then 2/5) |
| Harness change | Verifier variants, cited evidence, thresholds |
| Measured | A bench of 377 graded finishes, 29 of them wrong. The kept verifier caught 22/29 with 6/348 false holds; a stricter variant caught 25/28 but held 33% of correct finishes and was rejected |

## Turn 2: the batch that looked like a win

| Step | What happened |
|---|---|
| Trajectories | A batch reported 11/14 (78.5%). Row audit: 456 of 482 verifier rounds errored, 421 from rate limits; 8 of 11 passes were grader rescues |
| Eval | Invalid-row accounting: provider, launch and substrate failures are classified and excluded from rates, never silently counted |
| Harness change | Adaptive backoff and a concurrency cap per deployment |
| Measured | In the next batch every task that submitted got a parsed verdict, and the audit moved on to six new root causes that the storm had hidden |

## Turn 3: cheaper calls, costlier trajectories

| Step | What happened |
|---|---|
| Trajectories | Late requests were 98.8% replayed content; per-call costs looked like the problem |
| Eval | Trajectory-level cost: total calls, steps and tokens to a correct end state, at equal pass rate |
| Harness change | Deduplication and early compaction were tried and measured on whole trajectories |
| Measured | Deduplication cut prefix bytes 29% but raised calls 56%. Low-threshold compaction raised total tokens 58.8% and 105.1%. On a context-mode screen, full replay used 19 calls where latest-exchange used 45. Full context was kept |

## Turn 4: the sweep where every row was read

| Step | What happened |
|---|---|
| Trajectories | A 29-task development sweep on a new lean core, with every row audited by hand |
| Eval | Row-level audit rules: any review error, silent mechanism failure or over-budget request is a defect, fixed before the next row |
| Harness change | 11 harness defects fixed with tests (see [run-loop engineering](run-loop-engineering.md)) |
| Measured | 18/29 solved at best attempt, 17/29 on the first valid attempt. Stated as a development sweep, not a comparison |

## What made the loop work

- **The eval came before the fix.** Each turn built the measurement first, so the fix could fail.
- **Invalid is not a failure, and not a pass.** Separating substrate failures from capability failures
  was what made turns 2 and 4 readable.
- **The loop ends in a decision.** Every turn ended in keep, kill or rerun, recorded in the
  notebook.
