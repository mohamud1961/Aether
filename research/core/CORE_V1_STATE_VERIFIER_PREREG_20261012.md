# Screen V1: state verifier vs transcript reviewer (pre-registered 2026-10-12)

## Question
Does a verifier that checks the **real state** in a disposable clone of the container (`--core-review state`, feea55877) catch wrong finishes that the transcript-reading reviewer (`reviewer_progress`) misses, without holding correct work?

## Basis (D1, 35 traces)
- **the reviewer finish review:** 0 of 3 confident wrong finishes caught (net-fit, seq-assembly, construct-assembly). It also held 2 correct finishes (cipher-diff-attack; that cause has since been fixed).
- **the reviewer progress holds:** 13 of 17 only said "incomplete".

## Arms (everything else identical: clm, REPL on, images on, GLM-5.3-Flash, effort high)
- `revp`: the reviewer progress reviews, plus the final and finish reviews (the D1 arm).
- `state`: no progress reviews. At finish, the verifier agent works in a clone; it holds only on observed failure, at most 2 holds.

## Board (×1 episode per arm)
- **Confident wrong finishes in D1:** net-fit, seq-assembly, construct-assembly.
- **Quickly solved in D1** (false-hold sentinels): repair-history, binary-extract, graph-query-catalog, credential-recovery-recovery, dual-language-build, cipher-diff-attack.

## Predictions (written before any V1 row ran)
1. **Catch:** on the 3 confident-wrong tasks, `state` holds at least 1 finish with a not_met entry whose observed output really shows the failure.
2. **Sentinels:** `state` holds at most 1 of the 6 quick tasks falsely (a hold on a row the grader then scores 1, without the hold changing the result).
3. **Solves:** `state` solves at least as many of the 9 tasks as `revp`. With n=1 per arm, a difference of ±1 is noise and will be reported as such.
4. **Cost:** the median verification takes 300 s or less, and the clone takes 60 s or less.
5. **Substrate:** 0 clone failures. Any clone failure is reported as a substrate defect, not as a verdict.

## Failure handling
Any failed prediction is recorded as failed. A hold counts as "real" only after I have read the verifier's command and output in the trace.
