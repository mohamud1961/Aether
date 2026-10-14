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

## Results (14 Oct 2026, 03:42–03:48Z at `f683e2da4`; 96/96 calls ok, 0 unmatched)

| Variant | Mid-point median reasoning | Zero-reasoning replies (of 24) | `finish` at 6 wrong | `finish` at 9 right | Finish-point median deliberation |
|---|---|---|---|---|---|
| control (high) | 219 | 12 | 6/6 | 9/9 | 0 |
| effort_none | 131 | 8 | 4/6 | 7/9 | 66 |
| effort_medium | 135 | 15 | 5/6 | 7/9 | 0 |
| effort_low | 77 | 18 | 6/6 | 8/9 | 0 |

- **S3-P1: FAILED.** `effort_none` mid-point median is 131 against control's 219, which is inside the ±50% falsifier. Its zero-reasoning replies went from 12 to 8, not to ≤ 6. Omitting `reasoning_effort`, as Terminus does, does not restore reasoning. Effort is not the switch.
- **S3-P2: HELD.** Low and medium reason no more than control; low reasons less.
- **S3-P3: FAILED, but not in the direction that matters.** `effort_none` finished at 4/6 wrong points (a change of 2). It also dropped right points 9→7, so it doesn't discriminate.

Decision: effort stays `high`. The live board S4 tests the analysis turn mode alone.

Cost: model $0.156 (≈ £0.125, metered, no unknown usage); VM time is counted with S4. Evidence: `audit_output/aether_s3_20261014/`.
