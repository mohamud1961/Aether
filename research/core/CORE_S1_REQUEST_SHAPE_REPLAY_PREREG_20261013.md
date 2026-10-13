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
