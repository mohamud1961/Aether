# Local facts overhead and lossless presentation candidate

The saved screen at `qa/evidence/facts_overhead_local_20261102.json` used
source commit `3559390d76ba8ee735dcbe901512149bd932427d`, three matched
scripted Core episodes, and a six-action synthetic task. It found a median
1.539 ratio for total request characters, 1.609 for p90 per-request characters,
and median local wall time of 2.635 seconds on versus 2.023 off. Median
environment executions were 49 versus 42. These are not provider tokens,
cloud cost, historical-task measurements, or Luna outcomes. The local screen
fails the previously identified overhead threshold and does not qualify a
default change.

The initial facts message alone was 1,702 characters in a separate local
inspection, including an 878-character list of command paths. Grouping
resolved commands by their identical containing directory would encode that
same synthetic list in 343 characters, before labels. Another repeated
section lists seven separate unmeasured versions.

## Bounded candidate and prediction

Present each group explicitly as `directory: command, command`, with any
nonstandard or withheld resolution printed individually. Preserve every
resolved command name and its exact path, every unresolved name, the
observation step, and all existing unknown/scope disclosures. Combine the
version line only when all its entries have the same unmeasured state. This
changes presentation, not the underlying collection policy. Do not suppress
observations merely to win a cost test.

Prediction: relative to commit `3559390`, the same local screen reduces median
total request characters by at least 8% and p90 request characters by at
least 8%. The new screen also reports wall time and execution counts without
claiming significance from three blocks. If any command/path, unresolved
name, observation age or unknown state is lost, the candidate fails regardless
of size. A model may misunderstand directory grouping, so a lossless textual
mapping does not establish behavior or task success; real matched task
outcomes and regressions remain necessary.

## Local result

At source `011a3cf7`, the repeated three-block synthetic screen produced a
median total request-character ratio of 1.410 and p90 per-request ratio of
1.465 (`qa/evidence/facts_overhead_compact_20261102.json`), reductions of
approximately 8.4% and 9.0% relative to the previous ratios. The predicted
presentation reduction was observed on this one synthetic workload. Median
local wall time was 2.499 seconds on versus 2.014 off, and environment
execution counts remained 49 versus 42. The fact channel still adds about
41% to the request characters in this screen; the default-overhead gate is
not met. The second run is neither a token-cost estimate nor a task-success
test, and the repeated screens are too small to establish latency effects.

## Recorded-request size sensitivity

At source `b0f59066`, 128 admitted historical runs and 3,319 captured worker
requests were examined read-only. Each run's initial command-name
availability was reconstructed from its own captured initial environment
brief and rendered as a new, separate state note; paths and all other missing
state were explicitly unmeasured. Keeping the original brief in place and
adding this one static note gave a median per-run total request-character
ratio of 1.0228 and a p90 per-request ratio of 1.1025. All 128 runs had a
usable initial brief for this calculation.

This is a counterfactual size sensitivity, not a replay of actual treatment
updates. It does not estimate state changes, model tokens, cache misses,
latency, provider spend, or task outcomes. It does not supersede the 1.410
ratio observed on the short synthetic workload. The recorded-request result
is `qa/evidence/facts_history_note_size_b0f59066.json`; its source and
limitations are frozen in `FACTS_HISTORICAL_REPLAY_CONTRACT_20261102.md`.
