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

## Amendment 2, 12 Oct ~02:00 UTC (during C2b row 1, before its result)

### Row 1 (v2) result
- **Not solved:** 2/3 grader tests, timeout.
- **Frame similarity now passes** (C1 failed it at 0.81).
- **Failed check:** the grader wants the line `I_InitGraphics: DOOM screen size: w x h: 320 x 200` in stdout. Doom's startup text was garbled, which points to a printf/varargs bug in the interpreter.

### Predictions
- **Pass:** P1 (max 29.9k), P2 (mean 16.0k), P3 (0 failures), P4 (3 reviews, 0 errors), P5 (9 REPL cells).
- **P6 failed in the good direction:** GLM made 3 accepted context edits, plus 2 checkpoints.

### Diagnosis
- **GLM** saw the garbled bytes in 4 tool results and never reasoned about them.
- **the reviewer** saw none of them. Its evidence was the solver's last 8 actions, and all 3 review requests lacked the program output.

### v2.2 changes
- The reviewer reads the tail of every terminal log and the newest REPL output itself, with non-printing bytes made visible.
- the reviewer gets a new malfunction question:
  - choices: garbled / errors / suspicious values;
  - findings are reported in progress and final reviews;
  - at confidence ≥ 0.8 it also holds a finish (still at most 2 holds).
- One generic solver-prompt line: unexplained output is a bug until explained.

### Schedule
- **C2b row 1** stays v2.1 (it measures `view_image`).
- **The rest runs on v2.2:** interpreter-build ×1, then verified-compiler-build ×1.

### New predictions
- **P11:** on each v2.2 review, output_logs are present in the reviewer request.
- **P12:** if the program output is garbled, at least one v2.2 review reports a malfunction.

## Post-run audit protocol (from 12 Oct ~01:55 UTC)
- **Every row** is audited with `tools/aether_program/core_audit.py` before the next change. It covers outcome, time split, steps, context, caching, tooling, verification, provider and cost.
- **Findings** are recorded here.

### Audit of C1 core_off vs C2 row 1 (v2), interpreter-build
| Dimension | C1 core_off | C2 row 1 (v2) |
|---|---|---|
| First file written | 525 s | 236 s |
| Mean / max input tokens | 25.7k / 55.7k | 16.0k / 29.9k |
| Cache ratio | 85% | 82% |
| Model / tool time | 832 / 667 s | 763 / 977 s |

- **Garbled output** was first visible at 311 s on v2; unnoticed for 25 min.
- **Urgent nudges** fired 10 times.
- **the reviewer verdicts** were all "incomplete" at 0.44–0.69, with only 2 coarse criteria.
- **C1 verified-compiler-build:** 660 s of `sleep` inside commands; finished with 3 min to spare.

### Added to v2.2 before its rows
- The urgent nudge fires at most once every 3 turns.
- The terminal description says to run long commands in the foreground with `wait_s`: the call returns at completion, unlike `sleep N`.
- The audit reports "not traced" for rows that predate retry tracing.
