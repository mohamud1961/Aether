# Q1: do qualified checks keep A1's detections without its harm? (pre-registered 15 October 2026)

## Why

A1 (13 Oct) showed checks written from the task before the work catch stated mechanical errors (credential-recovery 6/6) but
hold 42% of correct states. SpecHarness (arXiv 2609.29921; `CORE_FALSE_COMPLETION_PRIOR_ART_20261015.md`) lets
an obligation block only when it is grounded in the task and its validator is qualified on known cases, and reports
that this keeps correct runs (96.8% raw-pass preservation) while cutting false completion. Q1 tests that rule on
our own fixed states before anything reaches a run.

## Design

- Code: `1761a4a2a` (`aether.core.qualify`; the contract writer now also gives anchors and a violation per check,
  and keeps a check that needs a tool the task names as *pending*).
- Bench: `tools/aether_program/core_acceptance_bench.py`, unchanged cases (14 fixed states, labels proven by the
  official tests first), 3 writers per task (12 writer runs), GLM writer profile as in A1 (`glm-research-par-v1`,
  high), on the run VM. Development tasks only; held-out tasks untouched.
- Two scores per (state, writer) pair: **all checks** (A1's rule) and **hard only** (only qualified checks hold).
  The writer never sees a label or a planted state.

## Predictions (before any writer call)

- **Q1-a (harm, primary):** hard-only holds ≤ 3 of 24 correct-state pairs (A1: 10/24 with all checks).
- **Q1-b (detection kept):** hard-only holds ≥ 6 of 18 bad-state pairs, including ≥ 4 of the 6 credential-recovery pairs.
- **Q1-c (named tool):** in ≥ 2 of 3 seq-assembly contracts, a check calls `oligotm` and is kept as pending.
- **Q1-d (yield):** ≥ 11 of 12 writer runs produce a contract with at least one hard check.
Expected limits, stated now: graph-query-catalog and net-fit edge orientation are semantic and are not expected to be caught (A1
caught neither); a failed prediction is recorded as failed.

## Budget

GLM writer calls only; A1 cost ≈ $0.06. Kill at $0.50 recorded spend (a lower bound). VM time on the already
running the run VM (authorised for tonight).

## Amendment before the run (06:5x UTC): writer model

the run VM holds only the GPT-6-Luna key, so the writer is **GPT-6-Luna on the Responses API** (bench `--provider gpt-6-luna`,
`f3181d41a`), not GLM. A1's numbers (GLM) are therefore context, not the baseline: **the primary comparison is
within Q1**, all checks vs hard only, on the same contracts. Predictions unchanged. Smoke (1 writer, credential-recovery, not
part of Q1): 5/5 states right under both scores, its one check qualified hard, $0.0026.
