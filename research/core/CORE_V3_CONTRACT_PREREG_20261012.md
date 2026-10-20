# Screen V3: contract arm after the V2 fixes (pre-registered 2026-10-12)

## Why
V2 lost 6/18 rows to writer failures and seq-assembly lost most of each row to runaway reasoning turns. See the result section of `CORE_V2_CONTRACT_PREREG_20261012.md`. V3 tests whether the fixes remove those failures. It is not a promotion test: revp is not rerun, and the comparison is against V2's own rows.

## Setup
- **Code:** `a working branch` at the commit that adds this file.
- **Arms:** `CORE_V3_ARMS_20261012.json`, one arm `contract3`. Its flags are identical to V2 `contract`; the new name gives fresh run IDs.
- **Board:** the same 9 tasks, ×2 episodes, so 18 rows.

## Predictions
1. Writer failures: a contract reaches the worker (`contract_shown`) in ≥16/18 rows; 0 HTTP 400s; 0 writer deadline errors.
2. Runaway turns: no row has two consecutive turns that hit the output limit with no tool call.
3. Solve rate ≥ V2 contract (9/18).
4. Still not seen: ≥1 real catch (a hold on work the grader would fail, fixed by real work, and the row solves). This is read in the trace.
5. 0 rows where the worker edits what a check reads to make it pass.

Every row is audited. Any failed prediction is recorded as failed.

## Result: INVALID (substrate bug), audited 2026-10-12
The result is 7/18, $0.69. Not one row held a finish.

The audit found that the worker's commands were running inside the contract writer's clone; see the INVALIDATED section of the V2 file. A probe row with clone fingerprints and the Docker event stream proved it: the worker's terminal `cmd_N.sh` writes went to `aether-verify-<id>`, and its `write_file` went to a sibling clone.

Predictions are not scored, because the arm did not run as designed. Observations that do not depend on the bug:
- The writer's time cap worked. seq-assembly and construct-assembly got contracts in 3 of 4 rows, against 0 of 4 in V2.
- Low effort after a cut is honoured: 3 of 4 such turns acted within 25 s. One still ran to 32k tokens, so the follow-up turn is now also capped at 8k output tokens.
- The contract passed wrong work in net-fit e2, seq-assembly e1 and credential-recovery e2. In net-fit e2 the checks enforced everything stated, but not the answer the analysis has to find.
