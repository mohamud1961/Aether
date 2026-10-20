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

## Results (run on `c194749a`, 13 October, 14:10–14:17Z)

**Labels:** all 14 case labels were confirmed by the official tests. The net-fit ep 1 replay first failed to plant
because numpy was missing. The worker had installed it earlier in its run, so the fixture now replays that install
too (`c194749a`). Evidence is in `audit_output/aether_a1_20261013/`.

**Pairs (12 of 12 writer runs produced a contract; no row was error or unavailable):**

| Task | Bad pairs held | Good pairs held (harm) | Writers that separate bad from good |
|---|---|---|---|
| credential-recovery-recovery | 6/6 | 3/9 (all from w1) | 2/3 |
| net-fit | 4/6 | 4/6 | 0/3 |
| graph-query-catalog | 0/3 | 0/6 | 0/3 |
| seq-assembly | 3/3 | 3/3 | 0/3 |
| **Total** | **13/18 (72%)** | **10/24 (42%)** | **2/12** |

**Predictions:**
- **D1 held on the number (72% ≥ 60%), but the number is misleading.** seq-assembly's 3/3 and part of net-fit's holds come
  from contracts that also hold the correct state, so they are not detection. Only 2 of 12 contracts separate
  bad from good, and both are for credential-recovery.
- **D2 failed badly.** 42% of correct-state pairs were held, against a ceiling of 10%.
- **D3 held:** 12 of 12 writer runs produced a contract.
- **D4 held:** none of the 3 seq-assembly writers separated the B1 primers from the oracle.

**Why correct states were held** (from the check commands and their output):
1. **Literal reading of the task against what the grader accepts (net-fit, 3 writers).** The reference solution
   writes `from,to`; the task says `to,from`. The official tests accept the reference, and every writer's
   header check rejects it. A check that follows the task text exactly can still fail work the grader passes.
2. **Wrong assumptions about where things are (credential-recovery, w1).** The check required each answer to appear
   in `*.bin` files, but the evidence is in a `.dat` file.
3. **Domain re-implementation errors (seq-assembly, all writers).** The task names primer3's `oligotm` as the ground
   truth. The writers reimplemented melting temperature in perl and got wrong values (one reported "Tm
   617"), and also wrote their own BsaI rules.
4. **Writer logic errors (net-fit good, w1):** an edge-count assertion that is wrong for the intervened DAG.

**What it misses:**
- **graph-query-catalog:** 0/3. A wrong query passes every format or shape check. Catching it would mean re-deriving the
  answer, which the writer is told not to do.
- **net-fit:** the flipped-edge case passed 2 of 3 writers.

**Conclusion:**
- Pre-written checks reliably catch stated, mechanical properties: answer length, alphabet and fixed
  characters, 6/6. This is the class of the B1 credential-recovery ep 2 failure, and there the worker's own terminal
  had already shown it `len=14`.
- They do not catch semantic errors (graph-query-catalog, edge orientation).
- On correct work they misfire 42% of the time, through literal reading, wrong assumptions and domain
  errors.

Shown at finish as they are, these checks would push the solver to break correct work, which is the harm V4
already saw. **The finish-time display proposal is not supported, and nothing is promoted.**

**Accounting defect found:** the bench built the writers' provider without a call log, so writer usage was
not metered. Fixed after the run: each writer now logs to `<task>__w<n>.calls/` and rows carry
`contract.usage`. The A1 model cost is an estimate from the logged text: about $0.06, rounds 22, roughly 52k
output tokens. It is unmetered and may be low.

**Infrastructure:** the VM became unreachable at about 14:20Z, after the run had finished. Azure Resource
Health recorded "Unavailable, UserInitiated". It was shut down at 14:50Z with no matching activity-log entry,
and the cause is unknown. It was not Claude, and the principal confirmed it was not them. The VM was restarted
at 14:53Z to retrieve the evidence and deallocated at 14:55:10Z (verified).

**Cost:**

| Item | Cost |
|---|---|
| VM, about 49 min (14:04–14:50 and 14:53–14:55) | ≈ £0.30 |
| Model (estimate) | ≈ £0.05 |
| **A1 total** | **≈ £0.35** (stop was £0.60) |
| **Program cumulative** | **≈ £1.31 of £5** |
