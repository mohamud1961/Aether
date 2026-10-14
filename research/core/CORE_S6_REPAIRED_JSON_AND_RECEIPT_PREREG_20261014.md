# Core S6: repaired JSON turns (x2r) and the finish receipt (r1) (preregistration)

Status: **SEALED by Claude on 14 Oct 2026, before any S6 model call.**

Authority: the principal's instruction of 14 Oct. Claude is in charge of the £7.

## Arms (each one change from the B1 baseline, flag-gated)

- **x2r** = `--core-turn json` at commit `95a5664a0`. This is S5's x2 interface plus two changes:
  - the reported repair of unclosed action objects and stray quotes;
  - unreadable replies no longer count toward the idle stop.
- **r1** = `--core-finish receipt` with native tool turns (commit `b612bf83d`). On the first `finish`, the model sees the heads of every file changed under the working directory since the start, and is asked to check them against each requirement. The next `finish` ends the work. The receipt is information, not a gate, and is shown once.

  **Why:** the S4 and first-divergence audits found final claims that the delivered bytes contradicted. net-fit b1 e2's summary says R→M while its file encodes M→R. Terminus's content-free "Are you sure?" changed 0 of 13 outcomes.

## Board and comparison

- **Board:** the same 9 tasks × 2 episodes per arm, 36 rows, on the same route.
- **Reference:** S4's same-day b1 (12/18 solves; 4/16 wrong voluntary finishes, 25%; 2 timeouts) and S5's x2 (10/18).

## Predictions (recorded before running)

**x2r**

- **X-P1:** 0 runs stopped by the protocol. Every `no_tool_loop` stop in x2r counts against it.
- **X-P2:** ≥ 12 solves (at least b1's).
- **X-P3:** the wrong share of voluntary finishes is ≤ 25% (not worse than b1).

**r1**

- **R-P1 (primary):** the wrong share of voluntary finishes is ≤ 15%.
  - **Falsifier:** ≥ 25%, i.e. no better than b1.
- **R-P2 (mechanism):** in at least 2 rows, the model does more work after the receipt (any tool call besides `finish`).
- **R-P3 (harm):**
  - 0 rows where a state the grader would pass is changed into a failing one after the receipt. Audited from the trace: what changed after the receipt.
  - Timeouts ≤ b1's + 1.
- **R-P4:** ≥ 12 solves.

## Kill/keep

- **Keep a candidate default:** its primary prediction holds and solves are ≥ 12.
- **If both arms qualify:** they are combined only in a later, separately sealed batch.
- **No claim against Terminus without a fresh confirmation batch.** Even then, it is stated with its uncertainty: at n = 18, a gap of ±3 solves is noise (Fisher p = 0.50 for 12/18 vs 9/17).

## Budget

| Item | Estimate |
|---|---|
| Model | ≈ £1.5 |
| VM | ≈ £0.6 |

- **Hard stop:** £6.0 cumulative from the fresh £7. About £3.05 had been spent at sealing.
