# Held-out qualification: what Aether actually did

This directory contains the sealed September 2026 held-out qualification artifact used in the public funding/research story.

The important point is that it contains **wins, valid misses and invalid rows together**.

## Final H10 record

[`H10_FINAL_AUDIT_AND_READINESS_VERDICT_20260907.json`](H10_FINAL_AUDIT_AND_READINESS_VERDICT_20260907.json)

Recorded aggregate:

| Measure | Result |
| --- | ---: |
| Raw held-out tasks | 10 |
| Validly graded rows | 8 |
| Valid passes | 3 |
| Valid grader misses | 5 |
| Invalid infrastructure/provider rows | 2 |
| Benchmark retries | 0 |
| Reruns | 0 |
| Task substitutions | 0 |
| Mid-campaign tuning/repair | no |
| Solver parse errors | 0 |
| Solver continuation breaks on started rows | 0 |
| Demonstrated generic Aether production defects | 0 |

The sealed verdict is deliberately mixed:

- **Aether runtime mechanical integrity:** `ACCEPTED`
- **benchmark competitiveness:** `NOT_DEMONSTRATED`
- **performance verdict:** `NOT_COMPETITIVE_ON_H10_SAMPLE`

## Why publish a weak-looking benchmark sample?

Because the funding proposition is a research proposition.

Aether is not asking a funder to accept a claim that it already dominates current agents. The three-month programme is intended to determine which parts of the runtime preserve model capability, which parts merely add complexity, and whether matched comparisons support the design thesis.

A public evidence surface that only contains successful traces would make that research story less credible.

## What the H10 record does establish

Within this specific sealed campaign it establishes:

- the candidate was frozen before the campaign;
- each selected task consumed one attempt;
- invalid infrastructure/provider rows remained invalid;
- no failed task was substituted or rerun;
- no mid-campaign production repair was used to improve the board;
- the audited valid misses were not attributed to a demonstrated generic production defect;
- the runtime was mechanically strong enough to proceed to future research on untouched tasks.

It does **not** establish general benchmark competitiveness, superiority to another agent, or general safety.

## Particularly useful rows

- `configure-git-webserver` — valid pass, official reward **1.0**.
- `build-cython-ext` — valid pass, official reward **1.0**.
- `build-pmars` — valid pass, official reward **1.0**.
- `break-filter-js-from-html` — valid miss where an out-of-workspace action was correctly rejected; see [`../safety/workspace-boundary-rejection/`](../safety/workspace-boundary-rejection/).
- `batched-eval-parity` — invalid provider/host-infrastructure row, retained as invalid rather than converted into a model result.

The raw sealed JSON is the authority. This README is only a human-readable guide.
