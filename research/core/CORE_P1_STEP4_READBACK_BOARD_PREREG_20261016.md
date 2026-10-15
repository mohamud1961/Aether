# P1 step 4 — read-back on the B1 board (pre-registration, 2026-10-16)

Status: **SEALED by Claude before any step-4 model call.** Authority: the principal's "go, run it, audit incl reasoning
tokens too then stop for reviews" (2026-10-16), after step 3 (fresh short tasks) failed to reproduce the failure.

## Why this board

Step 3 showed GLM applies conventions correctly on short single-concern tasks (17/18). The failures studied in P1
happen in long tasks where the format or source requirement is far from the step that builds the file. The B1
board holds those tasks, and GLM fails them repeatedly at baseline, so reproduction is not in doubt. The fitting
risk (the lever was written after studying these failures) is handled by reporting studied and unstudied tasks
separately and by counting harm on tasks the baseline passes.

## Arms (same day, interleaved, same route as B1/S3–S6)

- `coreb1` — B1 flags (`--core-review off --core-context clm --core-repl on --core-images on`), unchanged.
- `rb1` — `coreb1` + `--core-readback on` (commit `564472446`; the paragraph names no task, file or error).

## Board

The B1 board (`<run-dir>/b1/run.sh` task list) **minus binary-extract** (task spec defect, excluded from
capability claims): 8 tasks × 2 arms × 2 episodes = **32 rows**. Each task's own timeout; Harbor graders after the
agent ends; 4 parallel rows. Task groups for reporting:
- **Studied failures (4):** net-fit, graph-query-catalog and the two sequence-design tasks.
- **Others (4):** the remaining board tasks (passed or failed for reasons P1 did not study).

## Predictions (recorded before any row)

- **S4-P1 (primary):** `rb1` solves ≥ `coreb1` solves + 3 (of 16). Falsifier: smaller gain. Honest prior: likely
  fails, like every earlier finish-time lever (S3–S6, N1, N2, Q1).
- **S4-P2 (mechanism, net-fit):** the delivered DAG file has the correct orientation under its header in ≥ 3/4 `rb1`
  net-fit rows versus ≤ 1/4 `coreb1` net-fit rows (audited from the delivered files). Recognition (the trace reads the file
  back by the header) and repair (the file is rewritten correctly) are counted separately.
- **S4-P3 (harm):** no task where `coreb1` solves 2/2 and `rb1` solves 0/2; `rb1` timeouts ≤ `coreb1` + 1.
- **S4-P4 (cost):** `rb1` mean token-priced cost per row ≤ 1.3 × `coreb1`.
- **S4-P5:** `rb1`'s share of wrong voluntary finishes is lower than `coreb1`'s.
- At n = 16 per arm a ±3 solve gap is noise (Fisher p ≈ 0.5 for 12/18 vs 9/17); any result is exploratory. No
  promotion to a Core default without a larger sealed confirmation.

## Audit (after the run, before any claim)

Per row: outcome, finish type (voluntary / timeout), wrong-finish label, cost, calls. For every `rb1` row: whether
the read-back happened (the trace re-reads a delivered file and interprets it by the task's words) and whether it
changed the file. **Reasoning tokens (GLM):** per arm and per outcome — reasoning tokens per call, share of calls
with ≤ 20 reasoning tokens, reasoning at the build step and at the finish step — descriptive only, no prediction.

## Budget

≈ $0.05/row on this board (S3–S6 actuals) → ≈ $1.6; VM ≈ $0.6. **Hard stop: $3 token-priced model spend.**
