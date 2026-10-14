# Postmortem: the 78.5 percent batch was a rate-limit storm

**What this is:** A postmortem of a 15-task parallel batch run on the Gen 3 line (architect, solver, verifier) in July 2026. Its closeout reported 11 of 14 completed tasks passing, a 78.5 percent success rate.
**Key result:** The verifier was almost entirely unavailable. In the audit's count, 456 of 482 verifier rounds errored, 421 of them with rate-limit errors, and 26 rounds (5.4 percent) returned a verdict. Eight of the 11 grader-passing tasks were not confirmed by the internal verifier.
**Why it matters:** The headline would have been the programme's first clean result. Its verifier denominator was mostly errors, so the number reflected the deployment's rate limit more than the harness.

## Timeline

| When (2026) | Event |
|---|---|
| 9 July, run A | 15 tasks launched in parallel on one model deployment (gpt-5.4-mini, effort medium). |
| 9 July, closeout | The closeout note records 14 of 15 tasks completed, 11 with reward 1.0 (78.5 percent), and two tasks lost to false-clean verifications. |
| 9 July, audit of run A | The audit finds the verifier non-functional for most of the batch and most passes grader-rescued. |
| 9 July, rerun | A rerun was started. It was incomplete at snapshot: 4 of 15 finished, 9 still running. A later post-run audit of the rerun traced the root causes below. |

## What the measurement claimed and what it showed

| Claimed | Reality |
|---|---|
| 11 of 14 completed tasks passed; 78.5 percent. | Of 482 solver-submit verification rounds, 456 (94.6 percent) errored without a verdict; 421 were rate-limit errors. |
| The internal verifier confirmed the passes. | Of the grader-passing tasks, 3 were confirmed by the verifier, and 8 were confirmed by the grader only (verifier completion misses). |
| The completion gate accepted only correct finishes. | The gate accepted two false cleans, at scores 0.98 and 0.93. Both were grader failures. The gate was necessary but not sufficient. |

The closeout counts 11 of 14 completed tasks. The audit describes the same 11 grader passes against 15 tasks, with one task terminated at step 0 by instruction. The two counts describe the same passes.

## Root causes

The post-run audit of the rerun traced five causes. Together they produced the storm.

1. **One deployment for every role.** The architect (which served as verifier) and the solver both resolved to one model deployment. Under sustained rate limits, verifier calls died on their 180-second deadline.
2. **Retries longer than the deadline.** The retry budget (300 seconds) was longer than the verifier's own timeout (180 seconds), so the retry ran into the deadline.
3. **Blocked verdicts with no path forward.** The verifier could return a blocked verdict that carried no findings. The solver could not act on it, and the stalemate detectors required findings, so they never fired. In the rerun's parsed verdicts, 13 of 20 were blocked with no findings.
4. **Verifier reads at the wrong root.** Three of the four verifier verdicts that asked for repair were built on reads at the wrong root or on a stale head.
5. **Solver blind to some results.** The solver did not see the results of non-command tools and resubmitted without new evidence.

The two audits differ in scope. The run-A audit covers the 482 verifier rounds. The post-run audit covers the rerun's six terminal runs, and it reports three of four passes as verifier completion misses, not eight of eleven. The directions agree; the exact denominators should be re-derived from the raw result files before either figure is reused.

## Fix

The audits named two fixes. Both were recorded as in progress at the time of the note, and this page does not record their completion.

- **Substrate.** Exponential backoff with jitter on rate-limit and server errors, and a per-deployment request limit. The rule adopted: no 15-way parallel runs on one deployment; serialise or cap concurrency.
- **Verifier.** An independence gate on completion evidence. A machine-checkable claim must cite an inspection of an independent kind (a re-run, a probe, or raw input), not the solver's own artifacts. The gate checks the kind of evidence, not the reasoning.

The post-run audit set an acceptance test for the rerun. The verifier should reach `completed` on at least three of the four stalemated tasks, blocked verdicts should fall to two or fewer batch-wide, and any new false clean on a grader-passing task would count as a failure of the fix.

## Lesson

A headline pass rate is only as good as its denominator. Before using a result, check three things: how many verifier rounds returned a verdict, whether each pass came from the internal check or only from the external grader, and whether the deployment was shared. This batch failed all three checks.
