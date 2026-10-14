# Case study 1: a 78.5% pass rate that was a rate-limit storm

**Date:** 9 Jul 2026. **Rule that caught it:** [governance rule 3](../governance.md#3-separate-verifier-review-gate-chosen-by-risk) (separate verifier) and [rule 4](../governance.md#4-evidence-tiers-before-promotion) (evidence tiers).

The harness reported a 15-task batch at "11/14 = 78.5% pass". The number looked like a win. An audit of the run rows showed that most of the passes were not confirmed by the harness's own verifier.

## What happened

Fifteen agents ran in parallel on one model deployment. The deployment rate-limited them. The verifier, which judges completion from task-visible state, could mostly not call the model at all. Its rounds errored and produced no verdict. The external grader then scored the solver's output, and the grader passed several runs that the verifier had never confirmed.

## How the workflow caught it

The audit read the rows in the order the rules required. It checked substrate health before judgement: how many verifier rounds returned a verdict, and how many solver steps were parse errors. Only after that did it count passes. It then crossed the official grader result with the verifier alignment for each row. A pass that the verifier never confirmed was counted separately as a verifier miss, not as a harness success.

## Numbers

- 456 of 482 verifier rounds errored. 421 of those errors were rate limits.
- 26 of 482 verifier rounds (5.4%) returned a verdict.
- 8 of 11 passes were grader-rescued (a verifier completion miss). Only 3 were verifier-aligned.
- On the worst tasks, 90 to 98% of steps were wasted in verifier-dead resubmit loops.
- A second failure: the completion-evidence gate accepted both false-clean completions, at 0.98 and 0.93. The gate was necessary but not sufficient.

## What changed

- Backoff with jitter, and a rate limiter, were added on 9 Jul.
- A completion-evidence gate that checks independence of the evidence kind was added on 9 Jul.
- The rule became: never run 15-way parallel on one deployment.
- The 78.5% figure was reclassified. The verifier-aligned count, not the grader pass rate, is the number to report.

## What it does not show

The verifier's judgement quality was not measured on this batch. Its rounds did not run. The batch shows the substrate failed. It does not show the verifier is good or bad. That question was carried forward and was still open at the time of writing.

