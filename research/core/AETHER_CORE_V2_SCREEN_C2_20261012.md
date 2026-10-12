# Aether Core v2: pre-registered screen C2 (12 October 2026)

- **Code:** commit `5897a3a4a`.
- **Design and decisions:** `tracking/ledger/inbox/20261012_aether_core_v2_raw.md`.
- **Contamination:** any later game-port-build row is **post-failure** and labelled that way.

## Arm
- `v2`: `--agent-mode aether-core --core-context clm --core-repl on --core-review reviewer_progress`.
- **Baseline:** C1 rows (Core v1, `project` context, no REPL), recorded in the ledger entry.
- **Scheduling:** one row at a time.

## Rows
1. **Smoke:** repo-secret-recovery. This container has no `python3`, so it exercises the "REPL unavailable" path.
2. interpreter-build × 2.
3. verified-compiler-build × 1. Regression check: C1 core_off solved it.

## Predictions (written before any v2 row)

| # | Prediction | Measured by |
|---|---|---|
| P1 | No request exceeds the 32k budget | Max provider `input` tokens per call ≤ 34k, allowing for the estimate |
| P2 | Mean input per call on interpreter-build is ≤ 20k tokens (C1: ~25k on core_off) | Run record |
| P3 | ≤ 5 provider 429s per row when rows run serially (C1: 31 and 95 failed attempts) | `provider_failures_by_status` |
| P4 | Every interpreter-build row gets progress@0.35, progress@0.7 and final reviews, with 0 review errors | `review_kinds` |
| P5 | GLM uses `python` for ≥ 3 cells on each interpreter-build row | `python_cells` |
| P6 | GLM **does not** edit its own context (0 accepted edits); the automatic checkpoint fires ≥ 1 time per interpreter-build row. Based on the earlier context-file arm, where GLM wrote zero notes | `clm` stats |
| P7 | interpreter-build: ≥ 1 of 2 solved (C1: 0/2, with core_off at 2/3 grader tests) | Grader |
| P8 | verified-compiler-build stays solved | Grader |

## Falsifiers and what follows
- **Any review error, any silent mechanism failure, or a request over budget:** a defect, fixed before any further row.
- **P5 fails** (python unused): the REPL is not adopted by GLM; report that, and consider removing the tool.
- **P7 fails and no row gets further than C1's 2/3 grader tests:** v2 shows no measured lift on interpreter-build. Make-doom is still run once as the post-failure comparison, labelled as such, not as a win.

## Budget
- **Spent so far:** about £0.6.
- **This screen:** 4 rows ≈ £0.6–1.0, plus VM time.
- **Stop line:** £4.50 cumulative.

## Amendment, 12 Oct ~01:25 UTC (during C2 row 1, before its result)

### New finding: the GLM deployment accepts images
- **Probe:** GLM answered three discriminating image probes correctly:
  - a teal fill;
  - left/right halves;
  - a square's position.
- **Control:** with no image sent, it said it saw none.
- **Why it matters:** the C1 interpreter-build failure was a wrong frame (similarity 0.81), which GLM never looked at.

### Change
- **v2.1** = v2 + the `view_image` tool (`--core-images on`), commit recorded below.
- **Row 1** (v2, already running) is kept and reported as v2.
- **Remaining rows:** interpreter-build ×2 and verified-compiler-build ×1, all run with v2.1 instead of v2.

### Predictions P1–P8 still apply, plus:
- **P9:** on each v2.1 interpreter-build row that produces a frame, GLM calls `view_image` on it at least once.
- **P10:** a v2.1 interpreter-build row whose frame is wrong is either fixed or reported as wrong; it is not finished as correct without the image being looked at.

### Mid-run observation (row 1)
- **P5 is at risk:** GLM ran Python only as one-shot terminal heredocs (2 of 53 terminal calls) and never used the REPL tool.
