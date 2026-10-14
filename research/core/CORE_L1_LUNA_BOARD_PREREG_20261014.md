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

## Results (14 Oct 2026, 13:45–14:26Z at `9dd673d6e`; 16 valid rows, 2 provider-blocked)

| Task | l1 e1 / e2 | (GLM x2r) | (GLM b1) |
|---|---|---|---|
| net-fit | **✓ / ✓** | ✗ / ✗ | ✗ / ✗ |
| seq-assembly | ✗ wrong / **✓** | ✗ / ✗ timeout | ✗ timeout / ✗ timeout |
| construct-assembly | ✗ wrong / ✗ wrong | ✗ / ✓ | ✗ / ✗ |
| repair-history | ✓ / ✓ | ✓ / ✓ | ✓ / ✓ |
| binary-extract | ✗ wrong / ✗ wrong | ✗ / ✓ | ✓ / ✓ |
| graph-query-catalog | ✓ / ✓ | ✗ / ✓ | ✓ / ✓ |
| credential-recovery-recovery | **invalid / invalid** | ✓ / ✓ | ✓ / ✓ |
| dual-language-build | ✓ / ✓ | ✓ / ✓ | ✓ / ✓ |
| cipher-diff-attack | ✓ / ✓ | ✓ / ✓ | ✓ / ✓ |

**Solves:** 11 of 16 valid rows (69%). **Wrong voluntary finishes:** 5 of 16 (31%). **Timeouts:** 0.

**Model verification.** Every one of the 18 rows' responses came from `gpt-6-luna-2026-09-22` (from `core_calls.jsonl`). The manifests record `core_provider: gpt-6-luna`.

**The 2 invalid rows.** Azure returned HTTP 400 `content_filter` (`ResponsibleAIPolicyViolation`) on the credential-recovery-recovery prompt after 4–5 turns. This is a provider policy block, not the harness or the model. It stays visible and uncounted. The filter settings were not changed (a security-policy change, out of scope).

- **L-P1: FAILED as written.** 11 solves, at the ≤ 11 falsifier.
  - Both invalid rows are on a task every arm passes; had they run, the count would have been 13 at most.
  - The rate (69%) equals b1's (67%).
- **L-P2: HELD.** 3 of 6 contested rows solved (net-fit 2/2, seq-assembly 1/2), against GLM's 0–1 of 6.
  - This includes the program's **first seq-assembly pass** with any harness or model.
  - Directional at n = 6 (Fisher exact, 3/6 vs 1/18 pooled over GLM's b1, x2r and T1: p ≈ 0.03).
- **L-P3: FAILED** (31% wrong).
- **L-P4: HELD.** 0 protocol stops, 0 unreadable replies (184 strict, 36 embedded, 0 repaired), and 0 harness-caused invalid rows.
- **L-P5: FAILED.** 8 of 10 valid saturated rows passed; binary-extract went 0/2.
  - **The failure mechanism:** in both episodes GPT-6-Luna assumed a `0x400000` load base for the PIE binary. It then "independently verified" its output with a parser built on the same assumption, and the grader found inconsistent values.
  - This is the same self-confirming check seen in GLM's seq-assembly and net-fit failures.

**Reading**

- **The domain wall on net-fit and seq-assembly was largely GLM's.** GPT-6-Luna crossed it at once.
- **The wrong-finish rate did not move** (31%). The model swap changed *which* tasks fail, not *how* they fail.
- **False completion through a self-designed, self-confirming check appears in both models.** It is a process problem that a stronger model does not remove.
- **Caveat:** L1 ran without reasoning continuity. On Chat Completions, GPT-6-Luna's reasoning is dropped every turn, while GLM's newest turn is replayed. L2 corrects that.

Cost: model $0.288 (≈ £0.23, metered token prices) plus smoke and probes ≈ $0.05. Evidence: `audit_output/aether_l1_20261014/` (main checkout).
