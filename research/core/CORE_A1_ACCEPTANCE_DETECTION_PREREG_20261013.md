# A1: can task-text acceptance checks detect B1's false completions? (preregistration)

Status: **sealed before any model call.** Claude wrote this on 13 October, after GPT-6-Astra's review of the
false-completion proposal (`49a2b16e2`). The principal approved the diagnostic ("go"). Spend is gated as shown below.

## Question

The current contract writer (`aether.core.contract.write`) reads only the task text and the untouched container.
Do the checks it writes fail B1's wrong final states and pass correct ones, including valid alternative formats?
This measures **detection only**. It does not show that the solver would repair its work, or that a
finish-time display causes no harm (GPT-6-Astra, finding 5).

## Cases (`tools/aether_program/core_fixed_states.py`)

Labels count only if the official tests agree with them (`--labels-only` runs first, with no model calls).
Cases whose labels disagree are excluded and reported.

| Task | Bad (expect hold) | Good (expect pass) |
|---|---|---|
| credential-recovery-recovery | B1 ep 2: joined fragments, 14 characters; V1: truncated, 11 characters | correct; **two candidates** (an allowed alternative); oracle |
| net-fit | B1 ep 1: the model's own final script, replayed; flipped R–M edge (the B1 ep 2 error class, from V1) | correct DAG; oracle |
| graph-query-catalog | B1 ep 1: query missing a professor | B1 ep 2 query (graded pass); oracle |
| seq-assembly | B1 ep 2 primers | oracle |

- **Not reconstructable:** construct-assembly ep 2. Its 2,700-nt gBlock was never printed in full and came from randomised
  code. This is recorded as a gap, not substituted.
- **Totals:** 14 cases: 6 bad and 8 good (first written as 9 good; GPT-6-Astra corrected it before any run). Each task gets 3 independent writers, and every writer's checks run on every
  case of that task. The good-two-candidates case is included because a whole-file rule would wrongly fail it.

## Predictions

1. **D1 (detection):** pooled over writers, at least 60% of (bad case × writer) pairs end as hold.
2. **D2 (no harm on correct work):** at most 10% of (good case × writer) pairs end as hold.
   That includes the two-candidate alternative.
3. **D3 (writer reliability):** at least 10 of 12 writer runs produce a contract without error.
4. **D4 (honest expectation):** seq-assembly is the hardest. At least 2 of its 3 writers fail to separate the B1
   primers from the oracle. Its requirement ("NEB-compatible sites") is domain knowledge, not a format.

A1 does **not** promote any mechanism. If D1 and D2 hold, the next step is a finish-time display experiment
with a matched control, which needs separate approval. If D2 fails, the writer is repaired before anything
else.

## Cost and stop

| Item | Estimate |
|---|---|
| Model: 12 writer runs at real meters | ≈ £0.15–0.30 |
| VM: about 30–40 min | ≈ £0.20 |
| **Hard stop for A1** | **£0.60** |

Cumulative program spend would be about £1.6 of £5. The VM is deallocated after retrieval.

## Amendment 1 (before any run): scoring semantics (GPT-6-Astra's review of `0fdf001e3`)

- Each (case, writer) pair now gets one of four statuses (`core_acceptance_bench.classify`):
  - **hold:** at least one executable check ran and failed;
  - **pass:** every check ran and passed;
  - **error:** a check could not run (exit 126/127, an interpreter error or a timeout) and no other check failed;
  - **unavailable:** no contract (writer error, empty contract or failed writer run).

  Before this fix, a missing contract counted as a hold, so it was credited as detecting every bad state.
- **Denominators are fixed at the scheduled pairs that survive the label step:** 6 bad × 3 writers = 18 bad
  pairs, and 8 good × 3 writers = 24 good pairs.
  - **D1:** holds / all bad pairs. Unavailable and error count as not detected.
  - **D2:** holds / all good pairs (harm). Unavailable and error are reported beside it, and never shrink the
    denominator.
  - **D3:** writer runs with a contract / 12 scheduled, reported separately.
- Every row is kept in `results.jsonl`, and `summary.json` holds all four counts per side. Tests:
  `tests/test_core_acceptance_bench.py`.
