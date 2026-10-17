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
