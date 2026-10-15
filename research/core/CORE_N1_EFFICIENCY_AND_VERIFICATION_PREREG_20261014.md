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

## Amendment 1 (15 October, ~00:00Z, during P1, before any P2 row)

**Smoke result (N1-P1e, sealed mechanism): mechanism held, detection failed.** Both `ev` binary-extract rows reached a
verdict (88 s and 79 s; 6 and 11 verifier steps; cost line present, clone cleanup ran) and both were **confirmed**.
Both rows were graded 0 (reward 0.0). So the verifier as sealed confirmed 2 of 2 wrong states.

Why (from the verifier traces and the call log):
1. It ran under the **solver's system prompt** ("complete the task… call finish when every requirement is met").
2. Its brief said another engineer "**says it is complete**", which is a completion claim (the reviewer bench measured
   claim-free review at 15/18 vs 10/18 with claims).
3. In both runs its first real action was reading the produced `extract.js`, whose comments state the invented
   "conventional 0x400000 image base"; it then rebuilt the image with that same base and called it independent.
4. It noticed that the task's example value could not be reproduced from the binary and explained it away
   ("illustrative"), exactly as the solver had. The grader uses the binary's own section addresses; the example comes
   from another binary, so neither its address nor its value is evidence about this input.

**Change (commit `33c846a31`, generic, nothing task-specific):** the verifier gets its own assessor prompt, a
neutral brief with no completion claim that lists the files changed during the work, and instructions to write down
what a correct result must contain before opening them, to treat produced code and comments as an interpretation,
and never to explain a contradiction away (run a distinguishing check or refute). The same contradiction rule joins
the solver's self-check paragraph (arm `b`). The baseline solver prompt is byte-identical.

**Consequences for the plan:**
- P2 arms `b`, `c`, `d` use the amended mechanisms (the flags are unchanged).
- **Smoke v2 before P2:** arm `ev` with the amended verifier on binary-extract × 2. Prediction **N1-A1:** at least 1
  of the 2 verifications is refuted, with evidence that names the address convention. Failure is recorded and P2
  still runs (the dev board is the real test), unless the verifier fails mechanically.
- N1-P2b's binary-extract clause and every other P2 prediction stand unchanged.
- The original smoke rows stay in the record as a failed detection of the sealed mechanism.

## P1 results (15 October, 00:13Z)

Board: 32 rows (`a`, `e` × 8 dev tasks × 2 episodes), 0 invalid, 0 timeouts; every row ended in a finish.
Rows: `<run-dir>/n1/p1/results.jsonl` on the run VM. Token-priced spend for P1 plus the first smoke:
$0.747 (≈ £0.56; estimate £0.95).

| Arm | Pass | Finish precision | Cache hit | Mean calls | Mean cost | Mean wall | Mean output tokens |
|---|---|---|---|---|---|---|---|
| `a` | 10/16 | 10/16 = 62% | 49.1% | 23.1 | $0.0312 | 392 s | 29,543 |
| `e` | 10/16 | 10/16 = 62% | 86.6% | 19.4 | $0.0143 | 296 s | 16,465 |

Predictions:
- **N1-P1a (cache): held.** `e` 86.6% (≥ 75%), `a` 49.1% (≤ 55%).
- **N1-P1b (steps): failed.** `e` 19.4 calls vs the bar of 17.3 (0.75 × 23.1); ratio 0.84. One row carries it
  (construct-assembly `e` e1: 111 calls); recorded as failed, not re-cut.
- **N1-P1c (cost): held.** $0.0143 vs the bar of $0.0234; ratio 0.46.
- **N1-P1d (no harm): held.** 10 vs 10 passes; the same tasks pass and fail in both arms.
- **N1-P1e (verifier works): held as a mechanism** (Amendment 1): both smoke rows reached a verdict, clone cleanup
  ran, cost line present. Detection failed (both confirmed wrong states); that is what Amendment 1 changed.

**Gate:** N1-P1d holds, so `e` is the P2 base.

**Wrong finishes (12, all with the verifier off), by the L1/L2 taxonomy.** The same three tasks fail in both arms;
the failures are the task's, not the efficiency flags':
- binary-extract × 4: **example value / open definition**: the address convention (one summary cites the example's
  start address 4194304 as "expected"); grader found 0% of its values.
- construct-assembly × 4: **picked source**: the fusion does not contain the sequence the grader expects at its
  start (order test). One `a` row finished while its own summary said the design "remains unverified".
- seq-assembly × 4: **open definition checked by self-written checks**: Tm 72.53 > 72, pair difference
  5.87 > 5, and twice "BsaI site ggtctc not found" (site orientation). Each summary claims these were verified.

Finish precision 62% on this host (L1/L2: about 73% on the 8-vCPU host; not compared, per the host rule).

## Amendment 2 (15 October, 00:25Z, before any P2 row)

**Smoke v2 (N1-A1): failed.** Both `ev` binary-extract rows (code `275cc74fd`) were confirmed by the amended verifier
and graded 0. The mechanism held again (verdicts in 77 s and 71 s, 9 and 8 steps, 1 produced file listed, cost
line present). This time neither verifier took the convention from the solver's code: both wrote their criteria
first and parsed the binary themselves, then **chose the same 0x400000 rebase on their own**, one citing the
task's example ("the sample's 0x400000 address supports normalizing"), which the contradiction rule forbids. Their
own maps matched the solver's output 700 of 700.

What this shows: on this task the wrong answer is **the model's own prior**, not something the verifier inherited.
A same-model verifier with no solver context reproduces it. Independence of context does not give independence of
error. This is the limit R1 measured ("weak where checking means solving again") seen from the other side. Not
changed again before P2: a third prompt edit tuned to one task would be fitting the smoke, and the sealed P2 board
is the test of whether the verifier catches the other failure classes (seq-assembly's checked limits, construct-assembly's source).

Verifier cost in the smoke: about $0.005 of a $0.009–0.011 row (≈ 45–50%). N1-P2e (≤ 25%) stands as sealed and
is expected to be at risk on short rows.

**P2 mechanics (no change to arms or predictions):** P2 runs arms `e`, `b`, `c`, `d` from
`CORE_N1_P2_RUN_ARMS_20261015.json` (`e` copied unchanged from the P1 arms file; `b`/`c`/`d` from the P2 arms
file) with `--episodes 3` into `<run-dir>/n1/p2`, whose `results.jsonl` is first seeded with the 16 P1
`e` rows. The runner skips measured cells, so it runs `e` episode 3 and the 72 `b`/`c`/`d` rows (80 rows),
interleaved under the same host conditions. Spend guard: P2 rows stop at $5.0 token-priced (≈ £3.8, under the
1.5× line of £4.05). Held-out list committed in `6a6519f7a`.

## P2 paused (15 October, ~01:00Z)

Paused by Claude after 13 new rows (P2 spend $0.21 token-priced) to redesign the finish and the verifier around
evidence rather than verdicts (the principal's direction: false work is systemic, not a model limit). Two rows in flight
(seq-assembly `b` e2, `c` e2) were killed and are not in the file. Completed rows stay in
`<run-dir>/n1/p2/results.jsonl` as a record of the paused design: net-fit 12/12 pass (all six
verifications confirmed, correctly); seq-assembly `b` e1 fail, `c` e1 fail **confirmed by the verifier** (grader:
"reverse primer must match an annealing site downstream of the forward primer"; the verifier checked the assembly
against its own circular reconstruction), `d` e1 **pass** (first seq-assembly pass in N1). No P2 prediction is
scored on 13 rows. Resumption, if any, is a new amendment.
