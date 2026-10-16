# P1 matched repair test (pre-registration, 2026-10-16)

Status: **SEALED by Claude before any model row.** Authority: the principal's "go … run the experiments audit them"
(2026-10-16) with the review instruction: cancel the 8 extra check-arm episodes (done before any started);
pre-register 36 runs; validate every starting graph state against the real grader; identical files, tools and
budgets in both arms; actual graph repairs primary, full-task success and regressions secondary; audit the final
files, not the model's claims; archive, deallocate; no expansion beyond the agreed budget without asking.

## Why

The live repair test (step 2) could not answer the question: its check arm needed GLM to break the graph *and*
the check to catch it in the same row; both valid check rows passed the check, so no check-arm row ever saw a
concrete failure. This test starts from **known broken files** instead.

**Question:** given its own broken graph files, does GLM repair them when told only to inspect and repair
(generic), and does a specific, verified contradiction (check) change that?

## Cases (real starting states; `eval_suite/repair_p1/generate.py`)

| Case | Source | Starting state (real grader: learned / intervened) |
|---|---|---|
| a | step 4 coreb1 e1 | learned correct; intervention dropped Y→D (P / F) |
| b | step 4 rb1 e2 (= step 2 nudge e3, byte-identical) | every edge reversed (F / F) |
| d | step 2 nudge e2 | learned correct; intervention removed Y→D, kept U→Y (P / F) |
| e | step 4 coreb1 e2 | D→Y and M→R against the task's tie-break; intervention not applied (F / F) |
| k1 | step 2 check e2 | control: both correct, `to,from` (P / P) |
| k2 | the reference solution's encoding | control: both correct, R `write.csv` (quoted, `from` before `to`) (P / P) |

Files are verbatim from each run's own `cat` output in its trace (k2 is constructed in the reference solution's
format). `eval_suite/repair_p1/validate_starts.py` runs the **real grader's** four graph tests on every starting
state: 6/6 as in the table (columns pass everywhere). No case ships a sample file (never kept), so every row must
(re)produce `final_bn_sample.csv`.

## Arms (instruction paragraph only; everything else identical)

Both variants: the original task text, then "A previous attempt at this task left its output files in /app:
learned_dag.csv and intervened_dag.csv (its sample file was not kept). Inspect this work against the task's
requirements and repair it, so that every required output file is correct when you finish."
- **generic**: nothing more.
- **check**: plus the output of `finish_checks/net-fit.sh` on the starting files ("An executed check … reported:
  …"). For a, b, d, e it names violations (b: U has parents and the intervention; a, d, e: the intervention). For
  e it does **not** name the two tie-break reversals (outside the check). For k1, k2 it reports no violation.

Same image (`alexgshaw/net-fit:20251031` + `COPY start/ /app/`), same task.toml (timeouts 3600 s), same
grader, same Core flags as B1 `coreb1` (no finish hold, no think reminder), GLM-5.3-Flash, the run VM, ≤ 3 parallel.

**Board:** 6 cases × 2 arms × 3 episodes = **36 rows**. Phase 0 (free, no model): one oracle row per variant
(12) must build and pass, proving the variant pipeline and grader work.

## Outcomes (audited from the graded final files, not the model's claims)

- **Primary — graph repair (broken cases a, b, d, e):** a row repairs when **both** grader graph tests pass on the
  final files (`test_learned_dag_structure` and `test_intervened__data_structure`). Partial: the test that was
  failing at the start passes at the end.
- **Secondary:** full reward (graphs + sampling + columns); **regressions** on controls k1, k2: a graph test that
  passed at the start fails at the end; timeouts; cost.
- The final graph files are read from the grader output and the trace's last write; a claim in the summary counts
  for nothing.

## Predictions (recorded before any row)

- **M-P1 (primary):** check repairs on broken cases ≥ generic repairs + 3 (of 12 rows each). Falsifier: smaller
  gap.
- **M-P2:** generic repairs ≤ 3/12 (consistent with step 2's 0/3 under a generic nudge).
- **M-P3:** check repairs ≥ 6/12 on broken cases (GLM acts on a named contradiction at least half the time).
- **M-P4 (case e, descriptive):** the check names only the intervention; if check rows fix the intervention but
  not the tie-break edges, that is evidence the model fixes what it is told and no more.
- **M-P5 (harm):** controls: 0 graph regressions in the check arm; generic regressions reported.
- Honest prior: S6 showed the bytes and got 0/18 corrections; the P1 probes showed recognition 18/21 when the
  requirement was named. This is the first test of *named contradiction → repaired file*.

## Decision rule

M-P1 fails with check repairs low → GLM does not act on even correct, named evidence; the next work is the
solver's response to contradictions, not check generation. M-P1 holds → step 3 (the solver derives its own
source-grounded checks) becomes the next proposal, for review.

## Budget

net-fit rows cost $0.01–0.10 (step 2: mean ≈ $0.03) → ≈ $1.1 for 36 rows; VM ≈ $1. **Hard stop: $2 token-priced for this
test** (within the night's agreed $3 total; step 2 + probes ≈ $0.7 so far). If spend reaches the cap, stop and
report; no expansion without asking.
