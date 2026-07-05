# Phase A result — Architect contract A/B (decisive)

Architect-only replay (no solver, no grader) across 10 tasks × 2 models × 2 variants.
Contract quality scored 0/1/2 against prompt-derived expectations (never the hidden grader).

| metric (0–2) | V1 mini (regex+repair) | V1 codex | **V2 mini (model contract)** | **V2 codex** |
|---|---|---|---|---|
| valid config | 10/10 | 10/10 | 10/10 | 10/10 |
| deliverables captured | 0.22 | 0.22 | **2.00** | **2.00** |
| output schema | 0.00 | 0.00 | **1.33** | **2.00** |
| thresholds | 0.00 | 0.00 | **2.00** | **2.00** |
| forbidden paths | 0.00 | 0.00 | **2.00** | **2.00** |
| executable checks generated | 1 | 1 | **18** | **22** |

## Findings
1. **Deterministic repair works** — mini's 8/10 architect *fallbacks* became *repairs* (`added:service_probe`): valid 10/10 for both variants, no generic fallback. Keep repair regardless.
2. **Only model extraction fills the contract.** V1 (repair on the regex pipeline) is still empty on content (deliverables 0.22, schema/thr/forbid 0.00, 1 check). V2 (model TaskContract) captures deliverables/schemas/thresholds/forbidden near-perfectly and generates 18–22 real checks.
3. **Model extraction reduces model-sensitivity.** V2 lifts *mini* to near-codex contract quality (deliv 2.00, 18 checks) — the weaker model no longer cripples the contract.
4. **Contracts are correct, not hallucinated** (spot-checked): raman → results.json + G/2D schema + protect graphene.dat; train-fasttext → model.bin + 150MB→157286400-byte check; openssl → all cert files + perm check + runs check_cert.py. Accuracy/rsa-bit thresholds correctly NOT turned into fake local checks.

## Decision
**Adopt V2 (pure-model TaskContract) as the architect; keep deterministic repair + validation.**
Model extracts the contract → schema validates → repair fixes inconsistencies → compiler emits
executable checks. Deterministic code never parses English; it validates and executes.

## Carried into Phase B
- Wire the contract architect into the kernel (flag-gated; baseline preserved).
- **Threshold fix:** only locally-measurable thresholds (file_size) may be gate-blocking;
  non-measurable ones (accuracy, rsa_bits) stay advisory in the contract — else the gate
  blocks on `missing_metric` forever.
- Gate hard rule: no `ready=True` with zero executed checks when checks/deliverables exist.
- Live check state to the solver (run planned checks each step → ✓/✗) + dynamic obligation
  status (pending→satisfied as artifacts land) + stop conditions / auto-submit.
