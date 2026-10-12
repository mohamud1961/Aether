# Screen V2: acceptance contract vs the reviewer progress (pre-registered 2026-10-12)

## Why
Screen V1 (same board): the state verifier made 0 catches, and on fixed known-bad states a verifier that judges a seen answer caught 1/6. Checks written from the task before any answer existed caught 6/6 to 10/12 on the same states (acceptance bench acc1–acc7). V2 tests the contract in the full loop, where false holds can be disputed.

Of 22 failed rows across D1 and V1, 12 ended with the worker calling finish on wrong work. That is the target.

## Setup
- **Code:** `a working branch` at 60105c2bf.
- **Arms:** `CORE_V2_ARMS_20261012.json`. revp (`--core-review reviewer_progress`, the current default) and contract (`--core-review contract`). Both use clm context, REPL on, images on.
- **Board:** net-fit, seq-assembly, construct-assembly, repair-history, binary-extract, graph-query-catalog, credential-recovery-recovery, dual-language-build, cipher-diff-attack. Same as V1.
- **Episodes:** revp ×1, contract ×2. That is 27 rows, `--max-parallel-rows 3`.

## Predictions (contract arm)
1. At least 1 real catch. A real catch is a hold on work the grader would have failed, after which the worker fixes it and the row solves. It counts only after I have read the failing check and the fix in the trace.
2. No row where the worker changed correct work to satisfy a wrong check and the grader then failed it.
3. At most 1 false hold per 3 rows on work the grader passes.
4. Solve rate of contract ≥ revp on this board (per-episode mean).
5. The contract reaches the worker before its first finish in ≥ 16/18 rows. Writing takes ≤ 300 s, with 0 writer crashes.

Any failed prediction is recorded as failed. Every row is audited: contract written, checks, holds, disputes, rulings, grader result.
