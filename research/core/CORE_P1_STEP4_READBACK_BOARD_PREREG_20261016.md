# P1 step 4 — read-back on the B1 board (pre-registration, 2026-10-16)

Status: **SEALED by Claude before any step-4 model call.** Authority: the principal's "go, run it, audit incl reasoning
tokens too then stop for reviews" (2026-10-16), after step 3 (fresh short tasks) failed to reproduce the failure.

## Why this board

Step 3 showed GLM applies conventions correctly on short single-concern tasks (17/18). The failures studied in P1
happen in long tasks where the format or source requirement is far from the step that builds the file. The B1
board holds those tasks, and GLM fails them repeatedly at baseline, so reproduction is not in doubt. The fitting
risk (the lever was written after studying these failures) is handled by reporting studied and unstudied tasks
separately and by counting harm on tasks the baseline passes.

## Arms (same day, interleaved, same route as B1/S3–S6)

- `coreb1` — B1 flags (`--core-review off --core-context clm --core-repl on --core-images on`), unchanged.
- `rb1` — `coreb1` + `--core-readback on` (commit `564472446`; the paragraph names no task, file or error).

## Board

The B1 board (`<run-dir>/b1/run.sh` task list) **minus binary-extract** (task spec defect, excluded from
capability claims): 8 tasks × 2 arms × 2 episodes = **32 rows**. Each task's own timeout; Harbor graders after the
agent ends; 4 parallel rows. Task groups for reporting:
- **Studied failures (4):** net-fit, graph-query-catalog and the two sequence-design tasks.
- **Others (4):** the remaining board tasks (passed or failed for reasons P1 did not study).

## Predictions (recorded before any row)

- **S4-P1 (primary):** `rb1` solves ≥ `coreb1` solves + 3 (of 16). Falsifier: smaller gain. Honest prior: likely
  fails, like every earlier finish-time lever (S3–S6, N1, N2, Q1).
- **S4-P2 (mechanism, net-fit):** the delivered DAG file has the correct orientation under its header in ≥ 3/4 `rb1`
  net-fit rows versus ≤ 1/4 `coreb1` net-fit rows (audited from the delivered files). Recognition (the trace reads the file
  back by the header) and repair (the file is rewritten correctly) are counted separately.
- **S4-P3 (harm):** no task where `coreb1` solves 2/2 and `rb1` solves 0/2; `rb1` timeouts ≤ `coreb1` + 1.
- **S4-P4 (cost):** `rb1` mean token-priced cost per row ≤ 1.3 × `coreb1`.
- **S4-P5:** `rb1`'s share of wrong voluntary finishes is lower than `coreb1`'s.
- At n = 16 per arm a ±3 solve gap is noise (Fisher p ≈ 0.5 for 12/18 vs 9/17); any result is exploratory. No
  promotion to a Core default without a larger sealed confirmation.

## Audit (after the run, before any claim)

Per row: outcome, finish type (voluntary / timeout), wrong-finish label, cost, calls. For every `rb1` row: whether
the read-back happened (the trace re-reads a delivered file and interprets it by the task's words) and whether it
changed the file. **Reasoning tokens (GLM):** per arm and per outcome — reasoning tokens per call, share of calls
with ≤ 20 reasoning tokens, reasoning at the build step and at the finish step — descriptive only, no prediction.

## Budget

≈ $0.05/row on this board (S3–S6 actuals) → ≈ $1.6; VM ≈ $0.6. **Hard stop: $3 token-priced model spend.**

## Results (2026-10-16, the run VM, commit `564472446`, 32 valid rows)

**Substrate notes.** The first 3 net-fit rows hit "Docker daemon is not running" (Docker restarted during VM boot); they
were rerun as attempt 2 by relaunching the same screen (`rerun.sh`, `s4r.log`). Infra-invalid rows are excluded.
The run directory `<run-dir>/s4` collided with the earlier S4 run (2026-10-14); its `run.sh`, `s4.log`
and arms were overwritten after being archived in `audit_output/aether_s4_20261014/`, and new rows append to the old
`results.jsonl` (filter arm ∈ {coreb1, rb1}).

| Task | Group | `coreb1` | `rb1` |
|---|---|---|---|
| net-fit | studied | 0/2 | 0/2 |
| seq-assembly task | studied | 0/2 | 0/2 (1 timeout) |
| construct-assembly task | studied | 0/2 | 1/2 |
| graph-query-catalog | studied | 1/2 | 2/2 |
| repair-history | other | 2/2 | 2/2 |
| credential-recovery-recovery | other | 2/2 | 1/2 (1 timeout) |
| dual-language-build | other | 2/2 | 2/2 |
| cipher-diff-attack | other | 2/2 | 2/2 |
| **Total** | | **9/16** | **10/16** |

Cost (token-priced, valid rows): `coreb1` $0.946 ($0.059/row), `rb1` $1.227 ($0.077/row) = **1.30×**. Total
step-4 spend ≈ $2.2 (under the $3 cap).

### Predictions

- **S4-P1 FAILED.** +1 solve (10 vs 9), not +3. Within noise.
- **S4-P2 FAILED** (and mis-specified: the board has 2 net-fit rows per arm, not 4). No net-fit row in either arm passed;
  `test_learned_dag_structure` passed in 1/2 rows per arm, so no orientation difference. Recognition without
  repair: `rb1` e2 read the file back, quoted the `to,from` header, interpreted each row ("U,D means D→U ✓") and
  ticked it, although its own reasoning had fixed U as having no parents. The check took the requested form and
  compared the file with the header, but not with the graph it intended.
- **S4-P3 FAILED on timeouts** (`rb1` 2 vs `coreb1` 0, limit +1); the 2/2→0/2 clause held (credential-recovery-recovery
  2/2→1/2). The credential-recovery timeout came from a slow recursive approach at 876 s; no read-back activity is visible
  near the end, so attribution to the lever is unclear.
- **S4-P4 HELD at the limit** (1.298× vs ≤ 1.3×).
- **S4-P5 HELD, weakly.** Wrong voluntary finishes: `coreb1` 7/16 (44%), `rb1` 4/14 (29%). But 2 `rb1` rows
  timed out instead; wrong-or-timeout is 7/16 vs 6/16, so the shift is mostly finishes becoming timeouts.

### Hand audit of the read-back

- **One genuine read-back repair:** graph-query-catalog `rb1` e1 re-read its delivered query, found that it had joined a
  country property on the wrong entity, fixed it, and passed. The matching `coreb1` e1 had no executor in the
  container, "verified manually" in its reasoning and finished wrong.
- **The construct-assembly win is not clearly the lever:** the row passed after rejecting an earlier decision recorded in
  its own notes (re-checking it against fetched evidence) and after an executed translation check that exposed a
  table bug. This is source re-checking and execution, not reading the delivered file by the task's words.
- **net-fit:** the lever produced the ritual (header quoted, rows interpreted) without the comparison that matters
  (file vs own intended graph). Same self-confirming pattern as N1/L1/L2.

### Reasoning tokens (GLM, descriptive)

| | `coreb1` | `rb1` |
|---|---|---|
| reasoning tokens / call (mean) | 557 | 836 |
| median per call | 0 | 0 |
| share of calls ≤ 20 tokens | 78% | 68% |
| finish-step reasoning (median) | 0 | 0 |

- **GLM reasons in bursts.** Most calls carry no reasoning; a few planning calls carry 1–5k tokens. Short
  mechanical tasks (repair-history) stay near 25 tokens/call in both arms.
- **The finish step is still reasoning-free in both arms** (median 0), as in T1/S1–S6: the lever moved where the
  model thinks during the work, not at the finish.
- **Loops are visible as zero-reasoning runs:** construct-assembly `coreb1` e2 made 693 calls, 359/371 with ≤ 20 reasoning
  tokens, and spent the most of any row ($0.27).
- When GLM checks, the reasoning states a conclusion and a tick ("✓", "Good.") instead of a comparison with an
  independent expectation. Reading the file was never the bottleneck; comparing it with an independent expectation
  was.

### Conclusion

The read-back paragraph does not move outcomes on the B1 board (+1, noise; 2 extra timeouts). It produced one real
repair (graph-query-catalog) and one ritual check (net-fit). Consistent with every earlier finish-time lever: instructions to check
make GLM *perform* checks, not *discriminate* with them. The lever stays built, off by default. GPT-6-Luna is not run
(S4-P1 and S4-P3 failed). The open question for review is whether any prompt-level lever can supply the independent
expectation, or whether that needs an executed oracle (e.g. a test the model writes *before* building, from the
task text only).
