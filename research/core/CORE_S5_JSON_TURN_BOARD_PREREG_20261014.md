# Core S5: JSON text turns, live, on the B1 board (preregistration)

Status: **SEALED by Claude on 14 Oct 2026, after S4's results and before any S5 model call.**

Authority: the same instruction as S4.

## Question

In S4's first rows, the analysis instruction under native tool calls (`x1`) barely changed how GLM works:

- it wrote text in about 40–50% of turns;
- its median output tokens per turn were 131, against b1's 141.

Terminus 2 has no function-calling interface. Every action must arrive inside a written JSON reply, with analysis and plan fields. S2's replay could only test that format on Aether's terse histories. S5 tests it live from turn 1.

## Treatment (one change of interface, flag-gated)

`x2` = B1's settings plus `--core-turn json` (commit `d0f6029bc`):

- The request has no tools parameter.
- Every reply is one JSON object: `analysis`, `plan`, `actions` (tool, args) and `task_complete`.
- Actions run through the same tools, validation, result saving and context mirror as native calls.
- All results return as one message.
- An unreadable reply is shown its parse problem. Three in a row stop the run, the same rule as idle turns.

## Board

- **x2 only:** 9 tasks × 2 episodes, the same board and route as S4.
- **Baseline:** S4's same-day `b1` arm (18 rows) is the comparison, with B1 (17 graded) as a second reference. This saves VM time.
- **Caveat:** b1 is not concurrent with x2. Provider conditions may differ by a few hours.

## Predictions (recorded before running)

S4's b1 arm solved 12 of 18, with 4 of 16 voluntary finishes wrong (25%) and 2 timeouts.

- **P1 (primary):** x2's wrong share of voluntary finishes is ≤ 15%.
  - **Falsifier:** ≥ 25%.
- **P2:** x2 solves ≥ 12.
- **P3 (mechanism):**
  - ≥ 90% of replies are readable (strict or embedded);
  - ≥ 90% of readable replies carry a non-empty analysis;
  - median output tokens per turn ≥ 2× b1's.
- **P4 (no harness harm):** ≤ 1 `no_tool_loop` stop, timeouts ≤ 4, and no crash, lost result or accounting gap.

## Kill/keep

- **Keep x2 as the candidate default:** P1 and P4 hold and x2 solves ≥ 12. A confirmation batch on fresh episodes is required before any claim against Terminus.
- **Kill x2:** P1's falsifier fires, or x2 loses solves to protocol failures.

Every row is audited, right finishes included.

## Budget

| Item | Estimate |
|---|---|
| Model, 18 rows | ≈ £1 |
| VM | ≈ £0.6 |

Hard stop: £5.5 cumulative from the fresh £7.
