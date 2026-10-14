# Core S3: does `reasoning_effort` suppress GLM's reasoning? (preregistration)

Status: **SEALED by Claude on 14 Oct 2026, before any S3 model call.**

Authority: the principal's instruction (13–14 Oct): "you have a fresh £7 / fix this issue / improve aether … better than every other agent (incl terminus)". Claude is in charge.

## Question

S1 and S2 replayed B1 decision points with the request settings changed, but every variant kept `reasoning_effort: "high"`. T1 (Terminus 2) sends no `reasoning_effort` at all. In T1, every turn reasons (median 2,022 completion tokens per turn). In B1, 67% of turns have zero reasoning.

GPT-6-Astra's S2 audit listed effort as a T1-vs-B1 difference that has not been isolated. S3 isolates it.

## Design

- **Points:** the S1/S2 points, built by the same `points()`: 15 finish points plus 9 mid points, from B1's `core_calls.jsonl`.
- **Variants:** four per point, each the recorded request with exactly one change (the control has none):

  | Variant | Change |
  |---|---|
  | `control` | none |
  | `effort_none` | `reasoning_effort` key removed |
  | `effort_medium` | effort set to medium |
  | `effort_low` | effort set to low |

- **Bench fix:** the provider's own params no longer refill a key the variant removed. Tested: red before the fix, green after.
- **Same as S1/S2:** model, deployment, credentials route and VM. One send per row. No tool runs.

## Predictions (recorded before running)

- **S3-P1 (primary):** `effort_none` raises the mid-point median reasoning to at least 3× control's, and has at most half as many zero-reasoning replies.
  - **Falsifier:** `effort_none`'s mid-point median is within ±50% of control's.
  - **My prior:** 35% that P1 holds.
- **S3-P2:** `effort_low` and `effort_medium` reason no more than control (median within ±50%).
- **S3-P3:** no variant changes the finish decision at wrong finish points by more than 1 of 6. S2 showed the false finish is a held belief; effort alone should not undo it.

## Use of the result

- If P1 holds, the live S4 board uses no `reasoning_effort`, and that is measured as its own arm.
- If P1 fails, effort stays as it is, and the live board tests the turn-format treatment alone.

Replay results never count as solve evidence.

## Budget

Model ≤ $0.25 (bench stop). VM ≈ 15 minutes. Total ≈ £0.3. Program budget: £7 fresh.
