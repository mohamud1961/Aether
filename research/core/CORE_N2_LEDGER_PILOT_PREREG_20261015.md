# N2: requirement ledger pilot — PRE-REGISTRATION (DRAFT, NOT AUTHORIZED)

Status: **draft awaiting the principal's explicit authorization**. No row may run before it, and the source below must be
re-sealed (exact commit, Linux qualification of `f85acbd83`/`d8de4e805` and the ledger on the run VM) first.

## Why

`CORE_WRONG_FINISH_DIVERGENCE_STUDY_20261015.md`: the recurring wrong finishes across harnesses and models sit on
requirements the task states explicitly, checked against the run's own reading. One minimal intervention against
that type: the requirement ledger (`--core-ledger on`, `916cef586`). Nothing else changes between the arms.

## Design

- Arms (`CORE_N2_LEDGER_ARMS_20261015.json`): `e` (N1's arm `e`, the concurrent baseline on this host) and `g` =
  `e` + `--core-ledger on`. Verifier off in both (one intervention at a time).
- Tasks (development board, recurring wrong finishes): construct-assembly, seq-assembly, net-fit, binary-extract,
  graph-query-catalog. Held-out tasks untouched.
- 2 episodes per task per arm = 20 rows; arm order interleaved per task; same model (GPT-6-Luna), host, limits,
  `--host-cpus 4 --max-parallel-rows 2`. One retry for infra-invalid rows only; cancelled and invalid rows stay in
  the denominator.
- Grading: the official grader, after the agent terminates. Model identity, deployment and response IDs are
  recorded per row from the call logs (not from launcher labels).

## Predictions (written before any row)

- **N2-a (mechanism):** every `g` row that finishes calls `requirements` at least once before its first finish;
  ≥ 80% of `g` rows quote every requirement sentence by their last ledger call.
- **N2-b (reading, primary):** wrong voluntary finishes on stated requirements (grader assertion on a requirement
  quoted in the task) are fewer in `g` than in `e`: `g` ≤ `e` − 2 of 10. Honest prior: uncertain; prompt-level
  levers failed six times (S1–S6, L1/L2).
- **N2-c (outcome):** `g` passes ≥ `e` + 1 of 10.
- **N2-d (cost):** `g`'s all-role token cost ≤ 1.5 × `e`'s.
- **N2-e (harm):** no task passed by `e` in both episodes is failed by `g` in both.
A null or negative result is recorded as such; n = 10 per arm supports a pilot reading, not a claim.

## Budget (sealed at authorization)

GPT-6-Luna token prices ($0.10 in / $0.01 cached / $0.50 out per 1M). N1 rows on these tasks cost $0.006–0.09; estimate
≈ $0.6–1.2 for 20 rows. **Kill rule:** stop if recorded model spend passes $2.0 (recorded spend is a lower bound;
the remaining £10 budget, ≈ £8.9 at most, is an upper bound). VM: ≈ 1.5 h on the run VM, deallocated after.
