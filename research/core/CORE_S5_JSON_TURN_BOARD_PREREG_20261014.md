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

## Results (14 Oct 2026, 05:33–06:09Z at `b6fd54930`; 18 valid rows)

| Task | x2 e1 / e2 | (S4 b1 e1 / e2) |
|---|---|---|
| net-fit | **✓** / ✗ wrong | ✗ / ✗ |
| seq-assembly | ✗ timeout / ✗ wrong | ✗ timeout / ✗ timeout |
| construct-assembly | **✓** / ✗ wrong | ✗ / ✗ |
| repair-history | ✓ / ✓ | ✓ / ✓ |
| binary-extract | ✓ / ✓ | ✓ / ✓ |
| graph-query-catalog | ✗ wrong / ✓ | ✓ / ✓ |
| credential-recovery-recovery | ✓ / ✗ wrong | ✓ / ✓ |
| dual-language-build | ✓ / ✓ | ✓ / ✓ |
| cipher-diff-attack | ✗ **protocol stop** / ✗ **protocol stop** | ✓ / ✓ |

- **Solves:** 10 of 18. This includes Aether's first construct-assembly pass on this program's boards (B1, S4, S5) and a net-fit pass.
- **Wrong finishes:** 5 of 15 voluntary (33%). Timeouts: 1. Protocol stops (`no_tool_loop`): 2.

Predictions:

- **P1: FAILED.** The wrong share was 33%.
- **P2: FAILED.** x2 had 10 solves.
- **P3: PARTLY HELD.**
  - Every readable reply carried an analysis.
  - Median output per turn was roughly 2–4× b1's (e.g. net-fit 423 vs 186).
  - Readable replies were 207 of 230 (90%), exactly at the bar.
- **P4: FAILED.** There were 2 `no_tool_loop` stops, both on cipher-diff-attack, and both caused by the harness.

**Diagnosis of the protocol stops (interface, not model judgment).** All 23 unreadable replies were audited:

| Kind | Count | Where |
|---|---|---|
| Action object left unclosed before the next action | 8 | cipher-diff-attack, binary-extract |
| Double quote left unescaped inside a string | 4 | construct-assembly, graph-query-catalog, seq-assembly |
| Prose with no JSON | 4 | dual-language-build e2, which recovered and passed |
| Empty, cut at the output limit | 7 | — |

My rule of three unreadable replies → stop ended both cipher-diff-attack rows, with about 25 minutes left. **That is the harness hindering the model.**

**Fix:** commit `95a5664a0`.
- A bounded, reported repair mends all 12 content-bearing slips offline. Each repair was inspected against the evident intent.
- Unreadable replies no longer count toward the idle stop.

**Decision:** x2 as run is not kept. The repaired interface (`x2r`) goes to S6.

Cost: model $0.668 (≈ £0.53, metered).
