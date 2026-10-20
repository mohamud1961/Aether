# S1 — does Aether's request shape suppress GLM's reasoning? (preregistration)

Status: **SEALED by Claude on 13 October 2026, before any S1 model call.** Authority: the principal's "go" to step 1
of the post-T1 plan (≈ £0.15 quoted; hard stop below).

## Question

In B1, 67% of GLM turns and 13 of 17 finish decisions had zero reasoning tokens; Terminus (T1, same model and
tasks) reasoned on every turn. Which of Aether's request differences causes this?

## Method

Replay of B1's recorded requests (`core_calls.jsonl`: exact messages, tools and params), one change at a time.
No tool is executed; only the model's next decision is recorded.

- **Points:** the final worker call of each B1 row that ended `finished` (15: 9 right, 6 wrong by the official
  grader), plus the middle worker call of 9 of those rows (all 6 wrong rows and the first 3 right rows by name).
- **Variants:**
  - `control`: the recorded request unchanged;
  - `auto`: `tool_choice: "auto"`;
  - `replay`: every earlier assistant turn gets back the `reasoning_content` its call returned (point skipped,
    and reported, if the history cannot be matched to the calls);
  - `parallel`: `parallel_tool_calls: true`.
- 1 call per point × variant. Same model, endpoint, credentials route and max_tokens as B1.
- **Measures:** reasoning tokens, output tokens, finish_reason, and the decision (calls `finish`, calls another
  tool, or text only).
- **Hard stop:** no new call once metered spend reaches $0.25; VM deallocated after the run.

## Predictions

- **S1-P1:** `auto` raises median reasoning tokens per point by ≥ 5× over `control`.
- **S1-P2:** `replay` and `parallel` each change median reasoning by < 2×.
- **S1-P3:** at the 6 wrong finish points, `auto` makes the model call `finish` less often than `control`.
- **Falsifier:** if no variant raises median reasoning ≥ 2×, request shape is not the cause; next suspects
  are the system prompt and the tool-result format.

## Not claimed

A single-decision replay does not show the run would then succeed. Any fix must still pass a matched board.
Temperature is 1.0, so one call per cell is noisy; the claim is about medians across points.

---

## Results (13 Oct 2026, 17:45–17:52Z at `e01f6c370`; 96/96 calls ok, 0 unmatched)

| Variant | Median reasoning | Zero-reasoning points | `finish` at 6 wrong points | `finish` at 9 right points | Text-only |
|---|---|---|---|---|---|
| control | 0 | 15/24 | 5/6 | 8/9 | 0 |
| auto | 0 | 18/24 | 3/6 | 5/9 | 4 |
| replay | 6.5 | 11/24 | 4/6 | 8/9 | 0 |
| parallel | 0 | 15/24 | 6/6 | 7/9 | 0 |

At the 15 finish points, reasoning stays near zero under every variant (most 0; max 239 control, 1626 for one
replay call). Mid-run points reason in all variants (up to 2,529) with no consistent variant effect.

- **S1-P1 (`auto` ≥ 5× median reasoning): FAILED.** Median 0 → 0.
- **S1-P2 (`replay`, `parallel` < 2× change): HELD** (medians 6.5 and 0 from a base of 0; no material effect).
- **S1-P3 (`auto` finishes less at wrong points): HELD numerically, not usefully.** 3/6 vs 5/6, but it also drops
  right finishes 8/9 → 5/9 and produces 4 text-only turns: less finishing overall, not better discrimination.
- **Falsifier triggered:** no variant raises median reasoning ≥ 2×. `tool_choice`, reasoning replay and
  parallel calls are **not** the cause. Next suspects, as preregistered: the system prompt and the turn format
  (Terminus requires written Analysis and Plan every turn and sends no tools parameter).

Cost: model $0.148 (≈ £0.12, metered, no unknown usage); VM 17:44:43–17:52:31Z ≈ £0.05. **S1 ≈ £0.17.
Program ≈ £3.06 of £5.** VM deallocated and verified. Evidence: `audit_output/aether_s1_20261013/`.
