# Screen V4: acceptance contract vs the reviewer progress on a fixed substrate (pre-registered 2026-10-12)

## Why
V2 and V3 contract rows ran on a broken substrate: compose routed the worker's commands into clones (see the INVALIDATED section of the V2 file). V4 is the first valid test of the contract.

Both arms run at the same code and get fresh run IDs, so revp's V2 rows (some of them V1 reruns) are not reused. The worker-side fixes apply to both arms: the low-effort turn after a cut (capped at 8k tokens) and malformed arguments replayed as `{}`.

## Setup
- **Code:** `a working branch` at the commit that adds this file.
- **Arms:** `CORE_V4_ARMS_20261012.json` (reviewerp4, contract4).
- **Board:** the same 9 tasks, ×2 episodes. That is 36 rows at `--max-parallel-rows 3`, about $2.

## Predictions (contract4)
1. At least 1 real catch. A real catch is a hold on work the grader fails, after which the worker fixes it with real work and the row solves. It counts only once read in the trace.
2. 0 rows where the worker changed correct work to satisfy a wrong check and the grader then failed it.
3. At most 1 false hold per 3 rows on work the grader passes.
4. contract4 solves ≥ reviewerp4.
5. `contract_shown` in ≥16/18 rows, and every round's `clone_unchanged` is true (the substrate check).
6. 0 rows where the worker edits what a check reads to make it pass.

Failed predictions are recorded as failed. Every row is audited.

## Result (audited 2026-10-13, all 36 rows read)
**contract4 12/18 vs reviewerp4 10/18.** Cost $0.94 vs $0.71. No infra failures. The 2-row gap is within noise at n=18.

| Task | contract4 | reviewerp4 |
|---|---|---|
| net-fit | 2/2 | 0/2 |
| graph-query-catalog | 2/2 | 1/2 |
| binary-extract | 1/2 | 2/2 |
| cipher-diff-attack, repair-history, dual-language-build | 2/2 each | 2/2 each |
| credential-recovery-recovery | 1/2 | 1/2 |
| seq-assembly, construct-assembly | 0/2 each | 0/2 each |

| # | Prediction | Outcome |
|---|---|---|
| 1 | ≥1 real catch | **Met (strong candidate).** cipher-diff-attack e1 was held twice, because its attack raised `RuntimeError: differential characteristic violated` when the check ran it in a fresh process; the worker fixed it and the row solved at 1379 s. repair-history e1 is plausible: a cherry-pick was held as "not merged", the worker redid it as a real merge, and the row solved. Neither first-finish state was graded, so neither is proven. |
| 2 | 0 correct work broken by a wrong check | **FAILED.** credential-recovery e1: the worker's answer `8XDP5Q2RT9ZK7VB3BV4WW54` matched the grader exactly. Check 1 wrongly required a `PASSWORD=` prefix and 32 characters. The worker rewrote its correct answer to satisfy the check instead of disputing, and the row failed. |
| 3 | ≤1 false hold per 3 good rows | Met: 2 rows (credential-recovery e1 and e2) of 13 rows with correct work. In credential-recovery e2, a dispute voided the wrong check and the row solved. |
| 4 | contract ≥ revp | Met (12 vs 10), not significant |
| 5 | `contract_shown` ≥16/18; clone unchanged | **FAILED** on coverage: 13/18 got a contract. Writer failures: seq-assembly e2, dual-language-build ×2 and construct-assembly e1 ran out of time; construct-assembly e2 submitted no checks. The substrate held: no worker file appeared in any clone. binary-extract showed only `out.json`, written by the writer's own checks, so checks can affect one another within a clone. |
| 6 | No editing what a check reads | Met. credential-recovery e1 changed its output, not the check's inputs; that is counted under prediction 2. |

Readings:
- First evidence of a finish-time catch.
- First evidence of the contract's cost: a wrong check plus a worker that complies instead of disputing.
- Writers still time out on the analysis-heavy tasks (seq-assembly, construct-assembly, dual-language-build).
- reviewerp4 net-fit 0/2 vs contract4 2/2 is the largest single difference; not yet read in depth.
