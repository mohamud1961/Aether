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

## Results (recorded 2026-10-14, after the board finished)

Evidence: `audit_output/aether_l2_20261014/` (main checkout; per-row harbor archives, `results.jsonl`, `l2audit.txt`).

| Task | e1 | e2 |
|---|---|---|
| net-fit | pass | pass |
| seq-assembly | **fail** | pass |
| binary-extract | **fail** | **fail** |
| cipher-diff-attack | pass | pass |
| repair-history | pass | pass |
| dual-language-build | pass | pass |
| construct-assembly | **fail (timeout)** | **fail** |
| graph-query-catalog | pass | pass |

**11/16, 0 invalid rows, model cost $0.456.** Per task, this is identical to L1. Reasoning continuity changed no task outcome on this board.

### Predictions

- **L2-P1 (≥ 12/16): not met.** It scored 11, so the falsifier (≤ 10) was not triggered either. This is the inconclusive band.
- **L2-P2 (contested ≥ 3/6): held.** net-fit 2/2, seq-assembly 1/2, construct-assembly 0/2. This is the same as L1, not an improvement.
- **L2-P3 (wrong share ≤ 25%): failed.** 4 of 15 voluntary finishes were wrong (27%). One of the four (construct-assembly e2) explicitly called its output a "provisional draft" and did not claim to have verified it. Claimed-verified-but-wrong is 3/15 (20%), but the sealed metric is 27%.
- **L2-P4 (mechanism real): held.** Encrypted reasoning was replayed in 287/287 eligible requests (100%). There were 0 provider 400s and 0 harness-invalid rows, and every call was served by GPT-6-Luna.
- **L2-P5 (binary-extract ≥ 1/2): failed.** 0/2.

### Failure audit

- **binary-extract ×2.** Both runs keyed the output at the task example's address, 4194304 (0x400000), by adding an invented base to a PIE binary. The grader found 0% of the expected values. Both runs noticed that the example's values do not match the file's bytes at that address, and finished without explaining the mismatch. Their checks compared the output against their own address mapping. All 4 binary-extract runs across L1 and L2 failed this same way.
- **seq-assembly e1.** This time the model ran the full assembly reconstruction, and it matched; L1's failure was abandoning that check. It failed instead on the primer Tm pair difference: 5.86 °C against a 5 °C limit. The grader counts overhang bases that also match the template as part of the annealing region. The model computed Tm only on its own definition of the annealing segment.
- **construct-assembly e2.** It never identified the antibody's antigen (anti-FLAG M2 → DYKDDDDK). It cycled through anti-GFP, anti-RAS and anti-ubiquitin guesses, then finished honestly as a "provisional draft" that the grader rejected.
- **construct-assembly e1.** Timeout. It also never identified the antigen. In its final ~480 s it launched a CPU-bound codon search with a 300 s wait, then waited again, and never wrote a fallback `gblock.txt`.
- **Context pressure.** Both L2 construct-assembly rows exceeded the 32k CLM budget (max 32.3k; 6 urgent nudges each, against 2–4 in L1). Replayed reasoning is excluded from the governed budget (`clm.held`), so this is not a continuity artefact. Whether the 32k budget hinders GPT-6-Luna is an untested hypothesis.

### Spend

Estimated cumulative ≈ £6.4 of the £7 (L2 model ≈ £0.35, VM ≈ £0.4). The VM was deallocated after the board.
