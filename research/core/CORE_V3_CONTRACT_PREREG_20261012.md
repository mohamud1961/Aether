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
