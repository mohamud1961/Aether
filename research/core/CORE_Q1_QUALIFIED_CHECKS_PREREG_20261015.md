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

## Results as run (06:16:57–06:29:50 UTC, f3181d41a; 12/12 writer runs produced a contract; $0.159 metered)

| Score | Bad states held | Correct states held (harm) |
|---|---|---|
| All checks (A1's rule) | 13/18 | 7/24 (29%) |
| Hard only (as run) | 4/18 | 3/24 (12.5%) |

- **Q1-a: held on the number (3/24), but invalid as a test** — see the defect below.
- **Q1-b: failed** (4/18; credential-recovery 2/6).
- **Q1-c: failed.** No check was kept as pending: all three seq-assembly writers mention `oligotm` but wrote checks that
  run without it (structure, BsaI sites, lengths); none called it.
- **Q1-d: failed.** 9/12 writer runs had at least one hard check (credential-recovery w1 and w3, net-fit w2 and w3 had none).

**Measurement defect (mine):** GPT-6-Luna wrote every anchor wrapped in curly quotes (`“It is exactly 23 characters
long”`), and `qualify.grounded` compared quote marks literally, so the task's own words were marked ungrounded
(credential-recovery 6, net-fit 9, graph-query-catalog 5 checks). The as-run hard-only numbers therefore do not test the rule. Fixed: quote
style and wrapping quotes are ignored (test added). A second gap: a perl check's own compile error ("aborted due to
compilation errors") was counted as a hold, not as "cannot run"; fixed (test added).

**Exploratory re-score (not pre-registered; same contracts and exits, fixed grounding, no model calls):**
hard only holds bad 8/18 (credential-recovery 4/6, net-fit 3/6, graph-query-catalog 1/3, seq-assembly 0/3) and correct 5/24 (21%; net-fit 2/6, graph-query-catalog 3/6).
The remaining harm is not invented facts but **grounded checks that read the task differently from the grader**:
net-fit's reference solution writes `from,to` where the task says `to,from` (A1's cause 1 again), and graph-query-catalog checks
match the query's text shape. Qualification screens out checks resting on invented facts; it does not separate
a correct reading from a wrong one, which is the dominant failure. Q1-R repeats the run with both fixes.

Evidence: `audit_output/aether_q1_20261015/q1_evidence.tgz` (sha256
22250308e89436635aab9f09dad079e9be50d59857f77d8efa9f82a7f456b971).

## Q1-R (pre-registered before its run): same bench and bars, fixed grounding and cannot-run

Fresh writers (3 per task), GPT-6-Luna, the commit that carries both fixes. Predictions, same bars as Q1:
**Q1R-a** hard-only harm ≤ 3/24 (expected to fail on the exploratory evidence: net-fit's to/from alone gives 2);
**Q1R-b** hard-only bad ≥ 6/18 with credential-recovery ≥ 4/6; **Q1R-d** ≥ 11/12 writer runs with a hard check. Kill $0.50.
