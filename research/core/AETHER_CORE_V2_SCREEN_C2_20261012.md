# Aether Core v2: pre-registered screen C2 (12 October 2026)

- **Code:** commit `5897a3a4a`.
- **Design and decisions:** `tracking/ledger/inbox/20261012_aether_core_v2_raw.md`.
- **Contamination:** any later game-port-build row is **post-failure** and labelled that way.

## Arm
- `v2`: `--agent-mode aether-core --core-context clm --core-repl on --core-review reviewer_progress`.
- **Baseline:** C1 rows (Core v1, `project` context, no REPL), recorded in the ledger entry.
- **Scheduling:** one row at a time.

## Rows
1. **Smoke:** repo-secret-recovery. This container has no `python3`, so it exercises the "REPL unavailable" path.
2. interpreter-build × 2.
3. verified-compiler-build × 1. Regression check: C1 core_off solved it.

## Predictions (written before any v2 row)

| # | Prediction | Measured by |
|---|---|---|
| P1 | No request exceeds the 32k budget | Max provider `input` tokens per call ≤ 34k, allowing for the estimate |
| P2 | Mean input per call on interpreter-build is ≤ 20k tokens (C1: ~25k on core_off) | Run record |
| P3 | ≤ 5 provider 429s per row when rows run serially (C1: 31 and 95 failed attempts) | `provider_failures_by_status` |
| P4 | Every interpreter-build row gets progress@0.35, progress@0.7 and final reviews, with 0 review errors | `review_kinds` |
| P5 | GLM uses `python` for ≥ 3 cells on each interpreter-build row | `python_cells` |
| P6 | GLM **does not** edit its own context (0 accepted edits); the automatic checkpoint fires ≥ 1 time per interpreter-build row. Based on the earlier context-file arm, where GLM wrote zero notes | `clm` stats |
| P7 | interpreter-build: ≥ 1 of 2 solved (C1: 0/2, with core_off at 2/3 grader tests) | Grader |
| P8 | verified-compiler-build stays solved | Grader |

## Falsifiers and what follows
- **Any review error, any silent mechanism failure, or a request over budget:** a defect, fixed before any further row.
- **P5 fails** (python unused): the REPL is not adopted by GLM; report that, and consider removing the tool.
- **P7 fails and no row gets further than C1's 2/3 grader tests:** v2 shows no measured lift on interpreter-build. Make-doom is still run once as the post-failure comparison, labelled as such, not as a win.

## Budget
- **Spent so far:** about £0.6.
- **This screen:** 4 rows ≈ £0.6–1.0, plus VM time.
- **Stop line:** £4.50 cumulative.
