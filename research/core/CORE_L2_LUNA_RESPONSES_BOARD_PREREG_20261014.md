# Core L2: GPT-6-Luna with native tools and reasoning continuity (preregistration)

Status: **SEALED by Claude on 14 Oct 2026, before any L2 board row.** Live probes (no board rows) checked that Azure accepts replayed encrypted reasoning with `store=false`.

Authority: the principal, 14 Oct: "did you turn on reasoning continuity, what about response id? worth turning on too?", then "go".

## Question

In L1, GPT-6-Luna ran with a handicap GLM never had. On Chat Completions its reasoning is dropped after every turn, and it had to act through JSON text, because GPT-6-Luna refuses tools while reasoning there. GLM gets its newest turn's reasoning replayed.

L2 gives GPT-6-Luna the same continuity GLM gets, plus native tool calls. The question: does GPT-6-Luna, set up properly, beat its own L1 score, and does continuity reduce the confident wrong finishes?

## Design

- **Arm l2:** `CORE_L2_ARMS_20261014.json`, the L1 arm with `--core-api responses` and native tool turns (no `--core-turn json`), at `6573d7e18`.
  - **Provider:** `responses.py`, stateless (`store=false`, `include=["reasoning.encrypted_content"]`).
  - **Replay:** the newest turn's encrypted reasoning, through the same `reasoning_content` slot and the same policies as GLM. CLM keeps only the newest turn's.
  - **Effort:** `high`, with a reasoning summary for the trace.
- **Board:** the L1 board minus credential-recovery-recovery, where Azure's content filter blocked both L1 rows. That leaves 8 tasks × 2 episodes = 16 rows, with the same pool, VM and parallelism (4).
- **Comparison:** L1 on the same 16 valid rows scored 11 of 16 (contested 3/6, wrong 5/16).
- **Recording:** the actual model is taken from `core_calls.jsonl`, and replay is audited from each later request's input items.

Two things change from L1 together, continuity and native tools. Separating them would take another board. The question here is GPT-6-Luna at its proper setting, not which of the two matters.

## Predictions (recorded before running)

- **L2-P1 (primary): ≥ 12 of 16 solves.**
  - **Falsifier:** ≤ 10.
  - **My prior:** 45%.
- **L2-P2:** contested rows (net-fit, seq-assembly, construct-assembly) ≥ 3 of 6 (no loss against L1).
- **L2-P3:** wrong share of voluntary finishes ≤ 25%. L1 was 31%.
- **L2-P4 (the mechanism is real):**
  - In every row with ≥ 2 worker calls, ≥ 80% of the requests that follow a turn that produced reasoning items carry encrypted reasoning items.
  - 0 provider 400s other than content filter.
  - 0 harness-caused invalid rows.
- **L2-P5 (exploratory):** binary-extract ≥ 1 of 2.

## Budget

| Item | Estimate |
|---|---|
| Model | ≈ $0.3–0.6 (L1's 18 rows cost $0.29; replayed reasoning adds input tokens) |
| VM | ≈ 1.2 h |

- **Kill rule:** model spend > $1.0.
- **Hard stop:** £6.9 cumulative on the fresh £7. About £5.65 had been spent at sealing.
