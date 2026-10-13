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
