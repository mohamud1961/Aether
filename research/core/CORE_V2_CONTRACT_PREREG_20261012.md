# Screen V2: acceptance contract vs the reviewer progress (pre-registered 2026-10-12)

## Why
Screen V1 (same board): the state verifier made 0 catches, and on fixed known-bad states a verifier that judges a seen answer caught 1/6. Checks written from the task before any answer existed caught 6/6 to 10/12 on the same states (acceptance bench acc1–acc7). V2 tests the contract in the full loop, where false holds can be disputed.

Of 22 failed rows across D1 and V1, 12 ended with the worker calling finish on wrong work. That is the target.

## Setup
- **Code:** `a working branch` at 60105c2bf.
- **Arms:** `CORE_V2_ARMS_20261012.json`. revp (`--core-review reviewer_progress`, the current default) and contract (`--core-review contract`). Both use clm context, REPL on, images on.
- **Board:** net-fit, seq-assembly, construct-assembly, repair-history, binary-extract, graph-query-catalog, credential-recovery-recovery, dual-language-build, cipher-diff-attack. Same as V1.
- **Episodes:** ×2 for both arms (the launcher applies `--episodes` to every arm; corrected before any row finished). That is 36 rows, `--max-parallel-rows 3`.

## Predictions (contract arm)
1. At least 1 real catch. A real catch is a hold on work the grader would have failed, after which the worker fixes it and the row solves. It counts only after I have read the failing check and the fix in the trace.
2. No row where the worker changed correct work to satisfy a wrong check and the grader then failed it.
3. At most 1 false hold per 3 rows on work the grader passes.
4. Solve rate of contract ≥ revp on this board (per-episode mean).
5. The contract reaches the worker before its first finish in ≥ 16/18 rows. Writing takes ≤ 300 s, with 0 writer crashes.

Any failed prediction is recorded as failed. Every row is audited: contract written, checks, holds, disputes, rulings, grader result.

## Result (audited 2026-10-12, all 36 rows read)
contract **9/18** vs revp **12/18** (revp e1 rows were reused V1 rows; the launcher re-used their run IDs). Cost $2.01 for all 36 rows.

| # | Prediction | Outcome |
|---|---|---|
| 1 | ≥1 real catch | **FAILED.** The two rows with holds both solved, but neither was a real catch. In repair-history e2, the worker made a failing check pass by truncating `.git/logs/HEAD`, the file the check's awk heuristic reads; only then did it do a real merge. In dual-language-build e2, both holds came from an awk double-precision check that a dispute correctly voided. |
| 2 | No correct work broken to satisfy a wrong check | Held |
| 3 | ≤1 false hold per 3 good rows | Held: 2 of the 9 graded-pass rows had false holds (repair-history e2, dual-language-build e2) |
| 4 | contract ≥ revp | **FAILED** (9 vs 12) |
| 5 | Contract reaches the worker before the first finish in ≥16/18 rows; writing ≤300 s; 0 crashes | **FAILED.** 6 rows had no contract. seq-assembly ×2 and construct-assembly ×2: the first writer call reasoned past the 300 s budget. binary-extract e2: a malformed `submit_checks` was replayed, then HTTP 400. dual-language-build e1: no check survived. |

Other defects:
- Weak contracts passed wrong work. repair-history e1: 1 check, because the main one was dropped for passing before the work. graph-query-catalog e1: 7 checks, but none tested the query result.
- credential-recovery e1: the finish was skipped as low_time at 829/900 s.
- The worker side: across the archive, 30 of 32 turns that reached the 32k output limit produced no action. seq-assembly lost 550–900 s per row to them, in both arms.

Fixes (1519ef98f and the next commit):
- Writer calls are capped at 150 s and retried at low effort after a cut.
- Malformed tool arguments are replayed as `{}` and reported; this applies to the worker too.
- The worker runs one low-effort turn after a cut-off turn.
- A `contract_shown` trace event.
- The contract text forbids editing what a check reads.

## INVALIDATED (2026-10-12, found in the V3 audit)
Every clone of the task container kept its Docker Compose labels, because `docker commit` copies them into the image. Harbor runs every command through `docker compose exec main`, and compose selected the clone while one existed.

- **Reproduced on the VM:** with an old-style clone alive, 3 of 3 `compose exec` calls ran in the clone. With the fix (labels blanked at commit), 3 of 3 reached the live container.
- **Consequence:** while the contract writer's clone was alive (its first 1–5 minutes) or a finish-check clone existed, the worker's terminal and file commands went to a throwaway container. That work was lost when the clone was deleted.
- **Symptoms seen in the audit:** the writer's checks "passed before any work", and repair-history and binary-extract lost work.

**The contract-arm results above, and the V1 `state` arm, measured a broken substrate. They are not evidence about the mechanism.** revp rows use no clones and are unaffected. Fixed in the next commit (`verify._UNLABEL`).
