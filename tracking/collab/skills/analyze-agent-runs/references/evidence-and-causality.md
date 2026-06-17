# Evidence and Causality

## Evidence Ranking

1. Official grader output and immutable result row.
2. Benchmark-native/container execution artifacts.
3. Raw tool observations, file hashes/deltas, process state, and model exchanges.
4. Replayed checks and verifier inspection receipts.
5. Observable reasoning/decision trace.
6. Summaries, handoffs, and analysis prose.
7. Prior hypotheses or public claims.

Higher-ranked evidence can overturn lower-ranked narratives.

## Claim Labels

- `OBSERVED`: directly present in an artifact.
- `INFERRED`: best causal explanation from multiple observations.
- `HYPOTHESIS`: plausible but unproven.
- `UNCLEAR`: evidence cannot distinguish alternatives.

## Root Cause Test

A proposed root cause should:

1. Occur before the downstream symptom.
2. Explain the following state transition.
3. Be plausibly preventative if removed.
4. Be more than a restatement of the final error.
5. Survive comparison with alternative explanations.

Example:

- Downstream symptom: required file missing at grading.
- Possible upstream causes: model call failed before execution; wrong path namespace; proxy completion; artifact sync failure; grader path defect.

Do not stop at “file missing.”

## First Decisive Divergence

Find the earliest step after which the pass path and observed path meaningfully separate:

- missing or misleading input;
- semantic misclassification;
- wrong tool or boundary;
- destructive action;
- ignored failure;
- self-confirming check;
- premature completion;
- runner/provider failure before model work.

Later mistakes may be consequences.

## Counterfactual Check

Ask:

> If this component had behaved correctly while everything earlier remained the same, would the task probably have recovered?

If no, it is likely contributing rather than primary.

## Trace Versus Promotion

Trace evidence shows why behavior changed. It does not prove general improvement.

Promotion requires a valid baseline, deterministic or official grader, target eval, regression sentinels, contamination controls, fresh end-to-end candidate runs, and an explicit keep/kill decision.

