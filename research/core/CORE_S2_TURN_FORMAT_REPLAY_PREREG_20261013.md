# S2 — does the turn format make GLM deliberate at finish decisions? (preregistration)

Status: **SEALED by Claude on 13 October 2026, before any S2 model call.** Authority: the principal's "go" to S2
(≈ £0.2 quoted; hard stop $0.25 model spend).

## Question

S1 ruled out `tool_choice`, reasoning replay and parallel calls: B1's finish decisions stay near zero
reasoning under every variant. T1's Terminus asks for written Analysis and Plan every turn and passes no tools.
Does the turn format, rather than the request knobs, decide whether GLM deliberates before finishing?

## Method

Same 24 B1 decision points and bench as S1 (`core_request_shape_bench.py`), one call per point × variant.

- `control`: the recorded request (re-sent, so S2 has its own same-session control).
- `analysis`: the recorded request with one generic sentence appended to the system prompt: before each action,
  write a short analysis of where the task stands against each of its requirements, what has been verified and
  how, and what remains; then act. Params unchanged (`tool_choice: required`).
- `analysis_auto`: the same sentence with `tool_choice: "auto"`, so written text is not squeezed out by a forced
  tool call.
- `json_turn`: no tools parameter. The system prompt keeps Aether's own text and adds Claude's own wording of a
  JSON turn format (`analysis`, `plan`, `actions`, `task_complete`), listing the same tools. History is rewritten
  into that format: earlier tool calls become JSON `actions`, tool results become user messages. No Terminus text
  is copied.

Measures: reasoning tokens; written analysis characters (content for `analysis*`, the `analysis` field for
`json_turn`); decision (`finish`/`task_complete`, other action, or text only).

## Predictions

- **S2-P1:** at the 15 finish points, at least one variant raises median deliberation (reasoning tokens +
  written-analysis characters ÷ 4) ≥ 5× over `control`.
- **S2-P2:** that variant finishes at ≤ 3 of the 6 wrong points while finishing at ≥ 7 of the 9 right points.
- **Falsifier:** if no variant moves finish-point deliberation ≥ 2×, the turn format is not the cause either;
  then diff full T1 and B1 runs turn by turn before any more spend.

## Not claimed

One decision per cell, temperature 1.0. A changed decision is not a solved task; any fix must pass a matched
board. Written analysis is counted, not judged for correctness.

---

## Results (13 Oct 2026, 18:05–18:13Z at `3826b67bd`; 96/96 calls ok, 0 unmatched)

| Variant | Finish-point median deliberation | `finish` at 6 wrong | `finish` at 9 right | Text-only | Mid-point median |
|---|---|---|---|---|---|
| control | 0 | 6/6 | 8/9 | 0 | 119 |
| analysis | 0 | 5/6 | 7/9 | 0 | 385 |
| analysis_auto | 338 | 4/6 | 7/9 | 3 | 228 |
| json_turn | 229 | 3/6 | 5/9 | 2 | 432 |

Deliberation = reasoning tokens + written-analysis characters ÷ 4.

- **S2-P1 (≥ 5× finish-point deliberation): HELD, but only from a base of 0.** `analysis_auto` and `json_turn`
  make the model write before finishing (median 338 and 229). With a forced tool call (`analysis`) it still
  writes nothing.
- **S2-P2 (≤ 3/6 wrong and ≥ 7/9 right): FAILED.** `analysis_auto` 4/6 and 7/9; `json_turn` 3/6 but only 5/9.
  Neither separates right from wrong better than chance on these points.
- **What the written analyses show:** at wrong points the model's analysis is detailed, confident and internally
  consistent, and it encodes the same error. net-fit e2: "intervened DAG — same DAG (intervention removes no
  structural edges)". graph-query-catalog e1: a careful hand cross-check of the wrong query. seq-assembly e2: a full design rationale.
  **The false finish is a held belief formed earlier, not a skipped thought at the finish.** More deliberation at
  the finish point does not correct it.
- **Mid-run deliberation stays far below Terminus** (best median ≈ 430 vs T1's ≈ 2,000 per turn) in every replay.
  All replayed histories are B1's own terse turns (tool calls with no analysis). A history of terse turns may
  keep the model terse; a single-decision replay cannot test that. It needs a live run with the turn format from
  turn 1.

Cost: model $0.165 (≈ £0.13, metered, no unknown usage); VM 18:04:40–18:14:00Z ≈ £0.06. **S2 ≈ £0.19. Program
≈ £3.25 of £5.** VM deallocated and verified. Evidence: `audit_output/aether_s2_20261013/`.
