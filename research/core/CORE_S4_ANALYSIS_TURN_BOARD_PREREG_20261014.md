# Core S4: analysis turns, live, on the B1 board (preregistration)

Status: **SEALED by Claude on 14 Oct 2026, before any S4 model call.**

Authority: the principal's instruction of 14 Oct ("you have a fresh £7 / fix this issue / improve aether … better than every other agent (incl terminus)"). Claude is in charge.

## Question

Aether finishes wrong far more often than Terminus on the same model and board:

| | Wrong share of voluntary finishes | Solves |
|---|---|---|
| Aether B1 | 6 of 15 (40%) | 9 of 17 |
| Terminus T1 | 2 of 13 (15%) | 12 of 18 |

The first-divergence comparisons found the critical errors visible in the run's own context. Requests settings and finish-time prompting don't fix it (S1, S2, S3).

The remaining difference with direct trace support: Terminus writes an analysis and a plan on every turn, from turn 1. Aether's turns are bare tool calls, and 67% of them carry no reasoning. A replay cannot test this, because a terse history may keep the model terse. S4 tests it live.

## Treatment (one change, flag-gated; the baseline is unchanged)

`x1` = B1's settings plus `--core-turn analysis` (commit `bdc0c5903`). Two things change:

- **System prompt:** one paragraph is appended, asking the model, before every call, to write:
  - what the latest results show, including anything that contradicts what it expected or what the task requires;
  - where the task stands against each requirement, and what has been verified and how;
  - what it will do next, and the result it expects.
- **Tool choice:** `tool_choice` becomes `auto`. In S2, a forced tool call suppressed the writing.

Everything else is identical to `b1`: source, tools, context mode, REPL, images, effort, model and deployments.

## Board and arms

- **Board:** the B1/T1 board. 9 tasks × 2 episodes per arm:
  - net-fit, seq-assembly, construct-assembly, repair-history, binary-extract;
  - graph-query-catalog, credential-recovery-recovery, dual-language-build, cipher-diff-attack.
- **Arms:** `b1` (a fresh baseline on the current source, to control for drift and sampling) and `x1`. 36 rows. The arms file is `CORE_S4_ARMS_20261014.json`.
- **Same route as B1 and T1:** `run_screen.py`, pool `pool_d1.json`, 4 parallel rows, each task's own timeout, and TB2.1 graders run by Harbor after the agent ends.
- **Grading:** neither Aether nor Claude grades.

## Predictions (recorded before running)

- **P1 (primary, false completion):** x1's wrong share of voluntary finishes is ≤ 20%, and below b1's.
  - **Falsifier:** x1 ≥ 30%, or x1 ≥ b1.
- **P2 (solves):** x1 solves ≥ b1 solves + 2. At n = 18 per arm this is a screen, not proof.
- **P3 (mechanism):** written analysis appears in ≥ 80% of x1 worker turns that make a tool call, and x1's median output tokens per turn are ≥ 3× b1's.
- **P4 (no harness harm):**
  - x1 has ≤ 1 `no_tool_loop` stop;
  - x1 timeouts are ≤ b1 timeouts + 2;
  - no crash, lost result or accounting gap in either arm.
- **P5:** b1 lands within ±3 solves of B1's 9 of 17. A larger swing means the board is noisier than assumed, and all comparisons are tempered accordingly.

## Kill/keep

Every row's trace is audited, right finishes included.

- **Keep x1 as the candidate default:** P1 holds, x1 solves ≥ b1, and P4 holds. A confirmation batch on fresh episodes follows before any claim against Terminus.
- **Kill x1:** P1's falsifier fires, or x1 loses solves to harness causes.

Failed predictions are recorded, not reinterpreted.

## Budget

| Item | Estimate |
|---|---|
| Model, 36 rows | ≈ £2.0 (x1 may cost more per row) |
| VM, about 2 h | ≈ £0.7 |

- **Hard stop:** £4.0 cumulative from the fresh £7, S3 included.
- **Deallocation:** the VM is deallocated when nothing sealed is running.

## Results (14 Oct 2026, 03:50–05:31Z at `d799b4f41`; 35 valid rows, 1 infra-invalid)

| Task | b1 e1 / e2 | x1 e1 / e2 |
|---|---|---|
| net-fit | ✗ wrong / ✗ wrong | ✗ wrong / ✗ wrong |
| seq-assembly | ✗ timeout / ✗ timeout | ✗ wrong / ✗ timeout |
| construct-assembly | ✗ wrong / ✗ wrong | **invalid** (credential fetch HTTP 502, no model call) / ✗ wrong |
| repair-history | ✓ / ✓ | ✓ / ✓ |
| binary-extract | ✓ / ✓ | ✓ / ✓ |
| graph-query-catalog | ✓ / ✓ | ✓ / ✗ wrong |
| credential-recovery-recovery | ✓ / ✓ | ✓ / ✓ |
| dual-language-build | ✓ / ✓ | ✓ / ✓ |
| cipher-diff-attack | ✓ / ✓ | ✓ / ✓ |

| | b1 | x1 |
|---|---|---|
| Solves | **12 of 18** | 11 of 17 graded |
| Wrong voluntary finishes | 4 of 16 (25%) | 5 of 16 (31%) |
| Timeouts | 2 | 1 |

- **P1: FAILED.** x1's wrong share is 31%, at or above the 30% falsifier and above b1's.
- **P2: FAILED.** x1 had 11 solves against b1's 12.
- **P3: FAILED** (from the first 7 rows, consistent later). x1 wrote text in about 40–50% of turns, and its median output per turn was no higher than b1's. Under native tool calls, the instruction barely changes how GLM works.
- **P4: HELD.** x1 had 0 `no_tool_loop` stops and 1 timeout. No harness loss in either arm. The invalid row is a substrate failure before any model call.
- **P5: HELD, at its edge.** b1 had 12 solves against B1's 9, a swing of +3. **This matters most:** the same baseline on the same board moved from 9/17 to 12/18 in a day. That equals Terminus's 12/18. The T1-vs-B1 gap was within noise (Fisher p = 0.50 for solves, 0.22 for wrong finishes).

**Decision: x1 is killed.** The baseline is kept.

**Pattern seen in x1's seq-assembly e1:** its own recheck flagged that part of the "annealing" region didn't match the template. The model called this "a bug in the recheck, not the primers" and finished. The grader then measured a 6.2 °C Tm gap.

Cost: model $1.788 (≈ £1.43, metered). The VM is counted with S5.
