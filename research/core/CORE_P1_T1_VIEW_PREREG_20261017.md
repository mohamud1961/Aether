# T1 field-aware view (two stages) — pre-registration (2026-10-17)

Status: **SEALED before any model call.** Authority: the principal's "GO: preregister T1, then run a small fixed-artifact
diagnostic followed by the matched repair experiment only if the diagnostic supports it. Keep the proposed $1–2 hard
cap and Core defaults unchanged. once done, audit, deallocate" (2026-10-17), after the ChatGPT review of the
check-lifecycle audit, whose design and safeguards are adopted below.

## Why

The lifecycle audit (`CORE_P1_CHECK_LIFECYCLE_AUDIT_PREREG_20261017.md`) found that 50/51 reversed final files never
met evidence able to expose them, while 13–14/15 contradiction episodes that did occur ended on the right side.
Hypothesis: a clearer view of what the delivered file *means* lets GLM's existing comparison ability fire. Reviewer
caution, adopted: a field-aware view is not independent evidence by itself; GLM must still compare it with source
facts. So two questions, two stages: (1) does the view help GLM *interpret* a fixed file? (2) does it change outcomes
in the normal workflow?

Safeguards (review): the view shows **literal named fields only** (`row 1: to=H, from=J`), never arrows, parent/child
words or a verdict; **no frozen or deliberately wrong expectations** in this experiment (detection and false alarms are
tested with correct vs reversed files instead). Core defaults unchanged; every change is flag-gated, default off.

## Stage 1 — fixed-artifact diagnostic (`tools/aether_program/view_probe.py`)

One plain text call per sample (no tools, nothing can be edited), with the solver's own client, deployment
(`FW-GLM-5.3-Flash-par`), sampling (temperature 1.0, top_p 0.95) and reasoning effort (high), via
`harbor_agent.build_provider`; credential from the VM managed identity, never printed.

Prompt (rendered offline, all 48 cells checked before sealing): the real P1 task text for the graph and format; a
"record of your session so far" with `cat /app/bn_model.py`, `print(model.edges())` (networkx order, as pgmpy prints
it) and the fitted CPDs in pgmpy's print format (OLS on the task's own data = the linear-Gaussian MLE); then
"You wrote /app/learned_dag.csv. It now reads:" followed by the file, and the question: decide whether the file,
exactly as delivered, satisfies step 1; reply with JSON `{"verdict": "satisfies" | "does_not_satisfy", "reason"}`.

- **Display arms:** `raw` = `$ cat /app/learned_dag.csv` output; `field` = `[view] /app/learned_dag.csv: CSV with
  header fields (to, from), N rows` + `row i: to=X, from=Y`. Everything else byte-identical.
- **Cells:** graphs g1–g6 × formats (`to,from`, `from,to`) × file (correct, column-reversed) × display = 48 cells ×
  **3 samples = 144 calls**, order shuffled (seed 17), ≤ 4 in parallel. **Stage-1 cap $0.60.**
- **Scoring:** right = (correct file, `satisfies`) or (reversed file, `does_not_satisfy`); unparsed = wrong. Per
  display and format: acceptance of correct files, detection of reversed files, **balanced accuracy** (their mean).
  Calls that still fail after the provider's retries are reported as missing (never silently dropped).
- **Grounding (descriptive, hand):** every `to,from` reversed-file answer (both displays) labelled: reason cites a
  source fact read with the right meaning (CPD parents / edge direction) vs not.

Predictions:
- **V-P1 (headroom):** `raw` balanced accuracy on `to,from` **< 90%**. If not, GLM interprets the delivered file
  correctly when asked, the view has nothing to fix, and **Stage 2 is not run** (finding: the comparison is not being
  made in-run, not a reading problem).
- **V-P2 (effect; Stage-2 gate):** `field` balanced accuracy on `to,from` **≥ raw + 15 points**, and `field`
  false-alarm rate on correct files (both formats) **≤ raw + 10 points**.
- **V-P3 (control):** `field` balanced accuracy on `from,to` ≥ raw − 10 points.

**Stage 2 runs only if V-P1 and V-P2 hold.**

## Stage 2 — end-to-end matched repair (conditional)

- **Treatment (`--core-view on`, default off):** after each `terminal`, `python`, `write_file` or `edit_file` call,
  Core lists delimited files (`*.csv`, `*.tsv`) under the working directory (depth ≤ 2) changed by that call and
  appends to the tool result the same field-aware rendering as Stage 1 (≤ 3 files, ≤ 20 rows each, then a count of
  the rest; values truncated). No instruction text, no verdict, no arrows, no task names. Code, unit tests (including
  a test that base prompts and results are byte-identical when off) and the commit are recorded in an amendment
  **before any Stage-2 call**.
- **Arms:** `coreb1` (as in the independent-check experiment) vs `vb1` = `coreb1` + `--core-view on`. Paired.
- **Board A′ (fresh graphs g7–g9, never used):** `to,from` 3 × 4 episodes × 2 arms = 24 rows; `from,to` 3 × 2 × 2 = 12
  rows; same supplied-model task and grader as the check board; checker validated on fixtures before any call; oracle
  run first.
- **B (harm screen):** the 6 TB tasks × 2 episodes × 2 arms, **only if V-S1 holds** and the cap allows.

Predictions:
- **V-S1 (primary):** on `to,from`, `vb1` reversed files **≤ `coreb1` − 3 (of 12)**, and `vb1` ≤ `coreb1` on ≥ 2 of 3
  graphs. `coreb1` < 3/12 → inconclusive.
- **V-S2 (mechanism):** in `vb1` rows where a view showed a reversed learned file, the model recognises it and repairs
  in **≥ 50%** of such rows (hand-read); views shown per row and false repairs (correct → wrong after a view) reported.
- **V-S3 (harm):** `from,to` `vb1` correct ≥ `coreb1` − 1 (of 6); B (if run) `vb1` solves ≥ `coreb1` − 1 of 12, no
  task down by 2, every regression hand-read.
- **V-S4 (cost):** `vb1` mean cost per valid row ≤ 1.5× `coreb1` on each board.

Decision (review): promotion requires improved final correctness **and** an observed inspection→repair mechanism
**and** no unacceptable harm or cost; even then, replication before Core. View helps Stage 1 but not Stage 2 → stop
improving the display; study why the comparison is not made. View does not help Stage 1 → no paid Stage 2.

## Budget, custody, audit

**Hard cap $2.00 token-priced for both stages** (Stage 1 ≤ $0.60). If the cap would be exceeded the run stops and is
reported **incomplete**; no cases are dropped to fit. Evidence: blob `p1-t1view-20261017/` and
`audit_output/aether_p1_t1view_20261017/`. the run VM is deallocated after the last run. Failed predictions are recorded
as failed.

## Stage 1 Results (2026-10-17, appended after scoring; predictions above unchanged)

**Custody.** `audit_output/aether_p1_t1view_20261017/`: `t1_s1.tgz` (results.jsonl, core_calls.jsonl, the 48 prompts),
`score_s1.py`, `grounding_labels.json`. Run from VM commit 26cee5dce (the sealing commit). **144/144 calls ok, 0
unparsed, 0 errors; $0.0179** (mean output 109 tokens, of which 41 reasoning).

| format | display | accept correct | detect reversed | balanced |
|---|---|---|---|---|
| `to,from` | raw | 18/18 | **1/18** | 52.8% |
| `to,from` | field | 18/18 | **18/18** | 100% |
| `from,to` | raw | 18/18 | 18/18 | 100% |
| `from,to` | field | 18/18 | 18/18 | 100% |

Per graph (`to,from` reversed detection): raw g1 0/3, g2 0/3, g3 1/3, g4–g6 0/3; field 3/3 on every graph.

- **V-P1 HELD** (raw `to,from` 52.8% < 90%): with the file shown raw, GLM accepts a reversed `to,from` file 17/18 times
  even when asked directly — a reading problem, not only a missing comparison.
- **V-P2 HELD** (+47.2 points; false alarms 0/36 field vs 0/36 raw).
- **V-P3 HELD** (`from,to` 100% both).

**Grounding (hand, `grounding_labels.json`).** Field: 18/18 reasons cite the model's edge direction with the right
meaning and apply the header to the file (one, g5 s1, also wrongly says row 1 is correct). Raw: 1/18 grounded; the 17
acceptances match the file's literal pairs to the `model.edges()` tuples ("exactly as returned by model.edges()")
without applying the header meaning — the same binding error as in the runs.

**Gate: V-P1 and V-P2 held → Stage 2 runs**, under the remaining cap ($1.98).

Limits: one fixed prompt shape; the file is shown in the same message as the source facts (in a run they are steps
apart); a reversed file is the only defect tested.

## Amendment 1 — Stage 2 implementation, recorded before any Stage-2 call (2026-10-17)

Predictions, arms, boards, cap and decision rules above are **unchanged**. This records how the treatment was built.

**Code: commit b5ccd0861** (on top of e323bef7d; deployed to the VM as branch `t1`, which is also the run's
`--integrated-ref`).
- `aether/core/view.py` (new, 101 lines); `loop.py` (+9: config field, session object, hook in
  `_invoke` around `_dispatch` for `terminal`/`python`/`write_file`/`edit_file`, a `view_files_shown` run metric);
  `harbor_agent.py` (`AETHER_CORE_VIEW` on|off, unset = off; recorded in the run record's config; still 500 lines);
  `tools/aether_program/core_arm.py` + `run_screen.py` (`--core-view`, core-only).
- **"Changed by that call"** is implemented as: content (`cksum`) differs from the previous listing. The first listing is
  taken just before the first viewed call, so files present before the run are shown only if they change. A file
  rewritten with identical bytes is not shown again. A change made between viewed calls (e.g. a background process) is
  shown after the next viewed call. Listing/read failures are traced (`view_error`) and show nothing.
- Rendering is byte-identical to Stage 1's `field` display for every Stage-1 file (24/24 checked, `view_probe.render`
  vs `view.render`; Stage 1 had one trailing newline more, which the tool result's own separator replaces).
- Known limit: `loop.py` was already over the 500-line cap (867 → 876); not decomposed in this slice.

**Tests.** `tests/core/test_core_view.py` (6): Stage-1 parity, row/value/file caps, only changed files shown
(depth, type, pre-existing and same-bytes cases), the model sees exactly the traced result, off runs no listing and
shows no view, env parsing. Core suite 237 passed / 29 skipped. Launch + screen arm tests 66 passed on a clean checkout
of the commit (in the shared worktree 13 launch tests fail only because of another session's uncommitted edit to
`run_tb21_glm_diagnostic.py`, which is not part of this commit or the VM tree). **Off = baseline:** a scripted
write/terminal/python/edit/finish run produces byte-identical model requests with this commit (view off) and with
e323bef7d (timings normalised).

**Board A′.** `eval_suite/role_p1/generate.py --board view`: `vw-g7..g9-{tofrom,fromto}`, seeds 3016–3018, graphs not used
in any earlier row (6, 6 and 7 edges); same task text, module, checker and grader shape as the check board. The `role`
and `check` boards regenerate identically (144 files, set contents compared). Checker validated on fixtures before any
call (`validate_view_board.py`): oracle → correct, reward 1; column-reversed and header-swapped → reversed, reward 0;
edge dropped → other; missing file → 0 — 30/30 as expected.

**Run order (VM the run VM, `run.sh`-style screen, two passes for infra-invalid cells):** oracle on all six `vw` tasks
(1 episode); then `to,from` 4 episodes × {coreb1, vb1}; then `from,to` 2 episodes × {coreb1, vb1}; then B only if V-S1
holds and spend + 1.5 × the archived coreb1 B cost ($0.56) stays under the cap. Spend so far $0.018; A′ projected
≈ $0.2 (archived check-board rows).

## Stage 2 Results (2026-10-17, appended after scoring; predictions above unchanged)

**Custody.** `audit_output/aether_p1_t1view_20261017/`: `t1_s2.tgz` (sha256 a3eab569…0364; screens pvo/pva/pvb, all
row archives, the two failed launch attempts), `score_s2.py`, `s2_rows.json`. Code 64fbaa050 (`--integrated-ref t1`).
Oracle 6/6. A′: 24 + 12 rows, **0 infra-invalid**, **$0.152**. Total T1 spend **$0.170** of the $2.00 cap. the run VM
deallocated after A′ (verified).

**Launch incidents (no model calls, $0).** Attempt 0 ran the chain as root: custody refused every row (git "dubious
ownership"). Attempt 1, as azureuser, failed in harbor with "Docker daemon is not running" although dockerd had not
restarted (cause not established). Both kept under `attempt0_*` / `attempt1_*`. Attempt 2 used the earlier runs' launch
form and an oracle gate (paid rows only if 6/6) and ran clean.

| board | arm | correct | reversed | mean cost |
|---|---|---|---|---|
| `to,from` | coreb1 | 8/12 | 4 | $0.0052 |
| `to,from` | vb1 | 4/12 | **8** | $0.0044 |
| `from,to` | coreb1 | 6/6 | 0 | $0.0031 |
| `from,to` | vb1 | 6/6 | 0 | $0.0030 |

Per graph (`to,from` reversed): coreb1 g7 0/4, g8 2/4, g9 2/4; vb1 g7 1/4, g8 4/4, g9 3/4.

- **V-S1 FAILED** (vb1 8 reversed vs coreb1 4; needed ≤ 1). Per the prereg, **B was not run**.
- **V-S2 FAILED.** The view showed a reversed learned file in **9/12** vb1 rows; **1/9 repaired** (g7 e3: next
  reasoning reads `row 1: to=G, from=D`, applies the task's header meaning, rewrites). In the other 8 the next turn went
  to the intervention / CPD details (7) or declared the files "written correctly" and finished (g9 e2); **no later turn
  in those 8 rows mentions the view**. False repairs: 0 (4 rows first viewed C, all ended correct).
- **V-S3 held** (`from,to` 6/6 both). **V-S4 held** (vb1 cost 0.85× on `to,from`, 0.97× on `from,to`).

**Reading the arm gap.** The view is shown only after a file changes, and vb1's system prompt is byte-identical to
coreb1's, so each row's first `learned_dag.csv` is written before any view exists. First states: vb1 **9/12 R**,
coreb1 **≈4/12 R** (3 R + 1 other, from the first printed readback — coreb1 has no views, so this is the first time the
file is visible, not necessarily the first write). The arm difference in outcomes is therefore almost entirely a
**pre-treatment first-write difference** (9/12 vs 4/12, Fisher two-sided p ≈ 0.1) — chance, not harm by the view. The
treatment's own effect is 1 conversion in 9 exposures.

**Decision (per the reviewer's rule):** the view helps Stage 1 (GLM asked to judge a shown file: 1/18 → 18/18) but
**not Stage 2** (shown the same rendering mid-run, unasked: 1/9 acted). **Do not promote; stop improving the display.**
The bottleneck is not the reading of the file once attention is on it, but **whether the comparison is made at all**:
in-run, a passive appended view is not attended to. `--core-view` stays in Core, default off.

Limits: n = 12 per arm per format; one task family; the first-write imbalance makes the outcome comparison
uninformative about harm at this n; the view only fires on change, so a file written once is shown once.
