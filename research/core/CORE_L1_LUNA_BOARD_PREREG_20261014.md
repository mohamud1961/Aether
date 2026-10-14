# Core L1: is the wrong-finish ceiling GLM's? Aether Core with GPT-6-Luna (preregistration)

Status: **SEALED by Claude on 14 Oct 2026, before any L1 board row.** The one-row smoke on repair-history, a saturated task, ran first. It checked the substrate only and is not counted.

Authority: the principal, 14 Oct: "do you think we should test gpt-6-luna?", then "run it".

## Question

S4–S6 left wrong finishes at 25–39% in every GLM arm, all on net-fit, seq-assembly and construct-assembly. Four finish-time mechanisms failed to move them.

The open question: is this GLM's ceiling, or a ceiling of the task or the harness? HARNESS_VISION's one test says a better model must give a better system. L1 swaps only the model.

## Design

- **Arm l1:** `CORE_L1_ARMS_20261014.json`. It is the S6 x2r arm (JSON text turns, CLM context, REPL, images, review off) plus `--core-provider gpt-6-luna`, run at `9dd673d6e`.
- **Board:** the same 9 tasks × 2 episodes as S4–S6. Same pool, exclude list and VM. 4 rows run in parallel.
- **Why JSON turns:** GPT-6-Luna on Chat Completions refuses function tools together with `reasoning_effort` (probed live, 14 Oct). JSON turns send no tools parameter, so GPT-6-Luna reasons at `high`.
- **Like-for-like comparison:** GLM on the same interface scored x2 10/18 (S5) and x2r 10/18 (S6). The GLM tool-turn baseline b1 scored 12/18 (S4), and Terminus T1 scored 12/18.
- **Request shape** (substrate, not a mechanism): `max_completion_tokens`, no `temperature` or `top_p` (GPT-6-Luna rejects them), effort `high`.
- **Not run: a verifier-on arm.**
  - Core has no in-loop verifier that uses the solver's own model. `reviewer` is an external external evaluator model, and `contract` (pre-written checks) caused harm in 42% of A1 cases.
  - A same-model, fresh-context verifier must be built and sealed as its own step. That step would follow this result.
- **Recording:** the result row's `deployment` field is the screen's lane label (it reads FW-GLM-5.3-Flash-par). The audit takes the actual model from each row's `core_calls.jsonl` responses and the manifest's `core_provider`. A row whose responses are not GPT-6-Luna's is invalid.

## Predictions (recorded before running)

- **L-P1 (primary): GPT-6-Luna solves ≥ 13 of 18.**
  - **Falsifier:** ≤ 11.
  - **My prior:** 50%.
- **L-P2 (the ceiling question): GPT-6-Luna solves ≥ 2 of the 6 contested rows** (net-fit, seq-assembly, construct-assembly × 2).
  - **Falsifier:** 0 of 6.
  - **Reference:** x2r solved 1/6, b1 0/6 and T1 1/6.
  - **Interpretation:**
    - If P2 holds, the contested failures are at least partly GLM's.
    - If GPT-6-Luna also scores 0–1 of 6, those tasks are limited by the task or the harness. More GLM tuning there would be wasted.
    - At n = 6 this is directional evidence only, not a significance claim.
- **L-P3:** the wrong share of voluntary finishes is ≤ 20%.
- **L-P4 (substrate):**
  - 0 protocol stops;
  - 0 harness-caused invalid rows;
  - ≤ 5% of replies unreadable before repair.
- **L-P5 (no regression):** ≥ 11 of the 12 saturated rows pass.

No claim against Terminus follows from this board. It is a different model, and n = 18.

## Budget

| Item | Estimate |
|---|---|
| Model | ≈ $0.5–1.0 (GPT-6-Luna's Global Standard short rate: $0.10 input, $0.01 cached, $0.50 output per 1M tokens; the smoke row cost $0.0024 against GLM's $0.004–0.005 on the same task) |
| VM | ≈ 1.5 h |

- **Hard stop:** £6.9 cumulative on the fresh £7. About £5.5 had been spent at sealing, counting the VM since its 13:19Z restart.
- **Kill rule:** the board is killed if model spend passes $1.5.
