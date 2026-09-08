# Held-out qualification: H10

This is the most important aggregate evidence in the public release because it is not flattering.

The sealed 7 September 2026 H10 campaign used **10 held-out tasks** under a frozen candidate and frozen execution rules. It was not tuned during the campaign.

## Result

| Measure | Result |
| --- | ---: |
| Raw tasks | 10 |
| Validly graded rows | 8 |
| Valid passes | 3 |
| Valid grader misses | 5 |
| Invalid infrastructure/provider rows | 2 |
| Benchmark retries | 0 |
| Reruns | 0 |
| Task substitutions | 0 |
| Mid-campaign tuning/repair | 0 |
| Solver parse errors | 0 |
| Solver continuity breaks on started rows | 0 |
| Demonstrated generic Aether production defects | 0 |

The final sealed verdict says:

- **Aether runtime mechanical integrity: ACCEPTED**
- **Benchmark competitiveness: NOT DEMONSTRATED**
- **Performance: NOT COMPETITIVE ON H10 SAMPLE**
- **Benchmark execution readiness after host remediation: READY**

The complete machine-readable verdict is [`H10_FINAL_AUDIT_AND_READINESS_VERDICT_20260907.json`](H10_FINAL_AUDIT_AND_READINESS_VERDICT_20260907.json).

## Why publish a weak score?

Because Aether is a research project, not a leaderboard marketing exercise.

The campaign separates two questions that are easy to blur:

1. **Did the runtime mechanically do what it claimed?** The audit accepted that part.
2. **Did the model-agent system solve enough held-out tasks to be competitive?** No. Only 3 of 8 validly graded rows passed.

That distinction is central to the next research programme. The goal is not to rename model/task misses as harness failures, and not to hide infrastructure-invalid rows. It is to measure which system changes actually improve agent capability under frozen, matched conditions.

## Governance

The sealed record states:

- one attempt per task;
- zero benchmark retries;
- every row consumed exactly once;
- no substitutions;
- no H10 rerun authorized;
- no mid-campaign production tuning or repair;
- production diff from the frozen candidate after H10: `EMPTY`.

Two invalid rows exposed benchmark-environment/provider/host-infrastructure issues. They remain part of the final evidence rather than being silently replaced.

## What this supports

This supports a narrow credibility claim:

> By September 2026, Aether had reached a mechanically qualified runtime baseline suitable for further controlled experiments, while its held-out task performance remained clearly insufficient to claim benchmark competitiveness.

It does **not** support a claim that Aether is broadly better than existing agents.
