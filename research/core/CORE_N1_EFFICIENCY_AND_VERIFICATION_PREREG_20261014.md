# N1: an efficient solver that checks itself, and one independent check (preregistration)

Status: **sealed before any N1 model call.** Claude wrote this on 14 October. The GPT-6-Astra review gate was skipped at
the principal's instruction ("skip gpt-6-astra, go"; the bridge refused this project); the principal approved running it. Claude
wrote this on 14 October. Code: `79e7817c5` (verifier, self-check), `e82a6c858` (row labels), on top of `491a1216c` (key file),
`59252a02e` (`--core-reasoning all`) and `9d7655797` (`--core-calls many`).

## Goal (the principal's, 14 October)

The solver solves in as few steps as possible, checks its own work correctly, and submits. Verification happens
once, to confirm. The long-run aim is a solver whose self-check is trustworthy enough that the verifier is removed.
Efficiency (tokens, cost, steps) is a first-class result, not a side note.

**North-star number: finish precision** = graded pass rate among rows where the solver chose to finish (timeouts
excluded), for the solver *without* the verifier. L1 and L2: about 73% (4 of 15 finishes wrong in L2). The verifier is
dropped when finish precision is at least 95% on held-out tasks on two boards in a row.

## What is new, and what is not

Earlier evidence this board must respect:
- **R1 (13 Oct)** tested a fresh-context same-model reviewer (GLM) on a **bench**: 3/12 bad states held (25%), 1/16
  good states held, 11/28 runs hit the turn limit trying to re-solve. Strong where correctness is measurable from
  outputs; weak where checking means solving again; its one false hold came from tools missing in the fixture.
- **S3–S6 (14 Oct)**: effort, finish-time analysis, JSON turns and a finish receipt all failed to cut wrong finishes.
  Prompt-level levers at finish time have a poor record.
- **A1**: checks written before the work held 42% of correct states. Not repeated.

N1's verifier differs from R1 in four ways, each a stated reason it might do better: GPT-6-Luna instead of GLM; **in-run**,
on a clone of the solver's real final container (its installed tools are there); a brief that spends effort on the
failure classes seen in L1/L2 (example values, open definitions, picked sources, self-written checks) rather than a
full re-solve; and 40% of the remaining time (at most 600 s) instead of 24 turns. **Known gap:** the clone has no
network, so a wrong source (construct-assembly: the antigen sequence) can only be caught from the model's own knowledge.

## Mechanisms

| Arm flag | What it does | Status |
|---|---|---|
| `--core-calls many` | several tool calls per model turn, run in order | built, tested (`9d7655797`) |
| `--core-reasoning all` | every turn's reasoning replayed, so the request only grows at its end (cache) | built, tested (`59252a02e`) |
| `--core-self-check on` | one paragraph: name unobserved facts, check the riskiest against something not self-written, ask whether each check could have failed | built, tested (`79e7817c5`) |
| `--core-verify once` | at the first finish: clone, remove the solver's own files, a fresh Core run (own history, role `verifier`) checks the task; confirmed ends the work, refuted returns the evidence and the solver decides; never a second check; clone or verifier failure never holds the finish | built, tested (`79e7817c5`) |

All four are off by default; the baseline (`a` = L2's arm) is unchanged.

## Host and accounting

- Host: `the run VM` (Azure for Students, Denmark East), D3_v2, 4 vCPU, 13 GB. Runs use `--host-cpus 4`,
  `--max-parallel-rows 2`. L1/L2 ran on an 8-vCPU host, so **no N1 number is compared with L1/L2**; arm `a` is re-run.
- Model: GPT-6-Luna, Responses API, on the old account through the principal-placed key file.
- Every row reports: pass, finished/timeout, steps, input / cached / output tokens, cache-hit rate, cost, wall time;
  verifying rows also report verdict, verifier steps, time and cost (`extras.verification`).
- Prices as L2: $0.10 / $0.01 / $0.50 per M input / cached / output.
- Row labels now name the model called (`e82a6c858`); the lane is a separate field.

## Tasks

- **Dev (8):** net-fit, seq-assembly, construct-assembly, repair-history, binary-extract, graph-query-catalog,
  dual-language-build, cipher-diff-attack (L1/L2's board).
- **Held-out (12):** chosen **before P2 launches** by a fixed rule: the first 12 tasks of `pool_d1.json` in file order
  that are not dev tasks and not in `exclude.txt`. The list is committed before any P2 row starts and never changed.

## Phases, predictions and kill rules

### P1: baseline on the new host, efficiency, and one real verifier smoke (≈ £0.95)

- Arms `a` and `e` (= `a` + calls many + reasoning all) on the 8 dev tasks × 2 episodes: 32 rows.
- Smoke: arm `ev` (= `e` + verify once) on binary-extract × 2: 2 rows. This is a mechanism check on real Docker
  (clone, cleanup, verdict, cost line), not a capability claim.

Predictions:
- **N1-P1a (cache):** `e`'s cache-hit rate (cached / input, all rows) ≥ 75%; `a`'s ≤ 55%.
- **N1-P1b (steps):** `e`'s mean model calls per row ≤ 0.75 × `a`'s.
- **N1-P1c (cost):** `e`'s mean cost per row ≤ 0.75 × `a`'s.
- **N1-P1d (no harm):** `e` passes ≥ (`a`'s passes − 1).
- **N1-P1e (verifier works):** both `ev` rows record a verification with status confirmed or refuted (not error,
  skipped or no_verdict), the clone carries none of `/tmp/.aether`, and its cost line is present.

**Gate to P2:** `e` becomes the P2 base if N1-P1d holds; otherwise P2 drops the two efficiency flags (the P2 arms file
is regenerated and the change recorded). P2 needs N1-P1e; if it fails, the defect is fixed and the smoke re-run
before P2 (reserve).

**Calibration:** after P1 the principal reads the actual spend in the Azure portal. If real cost per row exceeds 1.3× the
token-price estimate, P2 and P3 are scaled down before launch.

### P2: self-check vs one independent check (≈ £2.7)

- Arms `b` (self-check), `c` (verify once), `d` (both) on the 8 dev tasks × 3 episodes = 72 rows, plus a third
  episode of the base arm (8 rows) so every arm has 3 episodes.

Predictions (base = `e`, or `a` per the gate):
- **N1-P2a (self-check, honest prior: likely to fail like S3–S6):** `b`'s wrong finishes ≤ base's − 2.
- **N1-P2b (verifier detects):** of `c` and `d` rows whose first finish is refuted, ≥ 60% end passing; and `c`+`d`
  pass binary-extract in ≥ 3 of 6 rows (base: 0 of 4 across L1/L2).
- **N1-P2c (verifier harm):** at most 1 of all `c`/`d` refutations is judged wrong in audit **and** followed by a
  failing row.
- **N1-P2d (system precision):** `c`'s and `d`'s finish precision each ≥ base's + 10 points.
- **N1-P2e (cost of the check):** verifier cost ≤ 25% of the row cost on average; verifier reaches a verdict in
  ≥ 85% of the checks it starts (R1: 61%).

Kill: if 2 audited-wrong refutations followed by failing rows occur before the board ends, `c`/`d` stop (rows not yet
started are cancelled and recorded as such).

### P3: held-out (≈ £2.4)

- The best P2 arm (highest finish precision; ties to the cheaper) vs base on the 12 held-out tasks × 3 episodes =
  72 rows. Reports finish precision for the solver alone (base, and `b` if it is the winner) and for the system.
- **N1-P3a:** the P2 winner's finish precision on held-out ≥ base's + 10 points.
- **N1-P3b:** the winner's correct finishes per £ ≥ base's.

## Audit (after each phase)

Every refutation and every confirmation of a failing row has its verifier trace read: is the evidence real (a
command and its output) and tied to a stated requirement? Every wrong finish without a verifier is classified by the
L1/L2 taxonomy (example value, open definition, picked source, self-written check, other). Verifier disagreements
are kept as the dataset for improving the self-check text (generic, never task-specific).

## Spend

| Item | Estimate |
|---|---|
| P1 (34 rows) | £0.95 |
| P2 (80 rows) | £2.7 |
| P3 (72 rows) | £2.4 |
| Reserve (infra re-runs, smoke re-run) | £1.5 |
| **N1 total** | **≈ £7.5 of the £10 GPT-6-Luna budget** |

Basis: L2 ≈ £0.022 per row; estimated at £0.03 per row, £0.035 with the verifier. Each phase stops at 1.5× its
estimate; N1 stops at £9 cumulative. The VM runs on the student credit and is deallocated after each phase.

## Interpretation rules

- 16–24 rows per arm cannot prove pass-rate differences; pass rate is reported, not claimed. Finish precision,
  refutation outcomes and efficiency ratios are the sealed measures.
- Failed predictions are recorded as failed. Invalid rows stay in the table with their reason.
