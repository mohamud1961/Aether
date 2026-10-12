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
