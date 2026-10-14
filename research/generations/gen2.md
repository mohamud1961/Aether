# Gen 2: receipt kernel

**What this is:** The second line. Every "done" claim had to carry a receipt, and a task-local profile (Adaptive Harness Profiles) was generated before the solve loop.
**Key result:** No line from this generation was promoted to a winner. The largest board scored 5 of 19 valid rows (26.3 percent) after 216 of 241 first attempts failed to launch. The one preregistered attribution tournament had a combined guard that passed its target rows and failed its sentinel.
**Why it matters:** The line produced the receipt vocabulary and the first honest accounting of invalid launches. It also showed that a control can hard-code the answer.

## Core idea

A harness should not accept "done" on the model's word. The kernel records a receipt for each claim, uses governed statuses, and keeps an evidence ledger. A small body of about ten tools covers shell, background jobs, files, waiting and completion.

## Design

```
task ─► AdaptationContract ─► validated run config (one adapter, no branches)
                                       │
            ┌──────────────────────────▼─────────────────────────┐
            │ solve loop: shell · jobs · files · wait · complete │
            │ every claim ─► receipt ─► evidence ledger          │
            └──────────────────────────┬─────────────────────────┘
                                       ▼
                       completion check (verifier, read-only)
```

- **Receipts and statuses.** Each claim is a receipt with a governed status.
- **Adaptation contract.** Visible requirements become completion-contract items; inferred requirements become verifier requirements; selected tools become the active schema.
- **Flags.** The profile was flag-gated, and the baseline path was kept.

## Evaluations

| Eval | Result | Decision |
|---|---|---|
| Attribution guard tournament, 3 tasks (2 target, 1 sentinel), 12 rows | Control 0/2 target and 1/1 sentinel; ignored-ID guard 0/2; no-call guard 1/2; combined guard 2/2 target but 0/1 sentinel. Total 6/12. | Combined guard kept for follow-up, not promoted. Ignored-ID guard killed. |
| Winner discovery across 7 families | No family won (winner count 0). | Closed. |
| Full board, 241 tasks times two attempts | 216 of 241 first attempts never launched. Valid-scored 5 of 19 (26.3 percent). Raw 5 of 241 (2.07 percent). | Launch-integrity fix; the raw figure is not a capability rate. |
| Five-homolog gate, two runs | 5 of 5 once; on the second run the verifier was not clean on any scoreable row. | Gate became repeated runs with verifier-clean as a required condition. |
| Targeted re-run of 14 rows | 6 pass, 4 fail of 10 scoreable; 0 false cleans; verifier not clean on all 6 passes. | Diagnostic. The verifier was the failure: it treated contract text as requirements and blocked read-only commands. |
| Adaptive Harness Profiles A/B | See the adaptive workbench page. | Kept as a flag-gated variant, not as a promotion explanation. |

## What was learned

- **Fake progress takes many forms.** Candidate lock-in, circular recovery and shape-only checks all passed the same surface tests. Receipts alone did not stop them.
- **Launch integrity comes before scores.** Most of the largest board was never scored, so the headline rate had to be stated as valid-scored only.
- **A control can be wrong in the same way as the thing it controls.** The guard that raised target rows regressed a sentinel in the same pattern each time.

## Why it was superseded

The line was demoted to a reference line on 3 July 2026. Its vocabulary (receipts, governed statuses, the evidence ledger) carried into later generations; its profile became one flag-gated variant, and its promotion claims were withdrawn.

