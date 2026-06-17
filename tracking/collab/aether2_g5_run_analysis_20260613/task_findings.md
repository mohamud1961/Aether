# Task-Level Findings (Failure Atlas)

Scope: every Attempt-1 attempt that is a failure, invalid, or unclear, plus the 5 passes for
completeness. Built from **valid Attempt-1 rows + authoritative grader output + frozen source
snapshot** (FAILURE ATLAS CONSTRUCTION). Attempt-2 entries are diagnostic-only.
All `loop_result.grader_reward` are `null`; authoritative verdict = `row_status`/`verifier_exit_code`.

Evidence shorthand: `R` = `rows/attempt1_rows_combined.jsonl` (`### FILE …/<task>/row.json`);
`S` = `scoreboards/…<task-era>…_scoreboard.md`; `P` = `progress.tsv`; `L` = `logs/attempt_1_<task>_.log`.

---

## PASS (authoritative, verifier_exit_code=0) — 5

| task | finalize | steps | note |
|---|---|---:|---|
| acl-permissions-inheritance | task_done | 6 | clean pass |
| analyze-access-logs | implicit_stop | 5 | pass even though loop ended implicitly |
| assign-seats | task_done | 6 | clean pass |
| attention-mil | task_done | 7 | clean pass |
| build-pmars | task_done | 20 | clean pass (medium SWE) |

Evidence for each: `R`,`S`,`P` (`rc=0`).

---

## VALID FAIL — verifier_exit_code = 1 (capability/harness signal) — 14

- **3d-model-format-legacy** (hard) — `implicit_stop`, 25 steps/27 calls. 39 pytest failures;
  `FileNotFoundError: converted_models/temp/cyberman.json`. Built/edited MdfLib converter but never
  produced valid JSON outputs; ran out of effort. Primary: execution/reasoning + timeout/step-budget.
  Advisory `clean=True` (false). Ev: `R`,`S`.
- **accelerate-maximal-square** (easy) — `implicit_stop`, 6 steps. `test_maximal_square`
  AssertionError: Numba DP **0.4× speed** (slower than vanilla; perf threshold missed). Genuine
  algorithmic shortfall, not budget. Primary: execution/reasoning (model capability plausible). Ev: `R`.
- **adaptive-rejection-sampler** (medium) — `implicit_stop`, 25 steps. Assertion "must be
  log-concave or envelope is poor". Numerical correctness shortfall. Primary: execution/reasoning. Ev: `R`.
- **aimo-airline-departures** (easy) — `task_done`, **3 steps**. 3/4 tests pass; `test_answer`
  wrong. Step-1 heredoc write returned **exit 126** (tool-contract anomaly worth a look). Stopped
  far too early. Primary: execution/reasoning (false-positive task_done). Ev: `R`.
- **amuse-install** (easy) — `task_done`, 16 steps. `ModuleNotFoundError: amuse.community`;
  install incomplete though venv created. Primary: execution/reasoning (false-positive). Ev: `R`.
- **ancient-puzzle** (easy) — `task_done`, 16 steps, `job_survival=False`. Failed grading.
  Primary: execution/reasoning. Ev: `R`.
- **audio-synth-stft-peaks** (medium) — `task_done`, 11 steps. Failed grading. execution/reasoning. Ev: `R`.
- **bank-trans-filter** (easy) — `task_done`, 3 steps. Failed grading; early stop. execution/reasoning. Ev: `R`.
- **blind-maze-explorer-5x5** (easy) — `task_done`, 15 steps, **advisory `clean=False`** (caught).
  `test_maze_map_contents` AssertionError. Uses `session_start`. execution/reasoning. Ev: `R`.
- **blind-maze-explorer-algorithm** (medium) — `implicit_stop`, 26 steps, advisory `clean=False`.
  Maze-map content mismatch. execution/reasoning. Ev: `R`.
- **bn-fit-modify** (hard) — `task_done`, 13 steps. Intervened-DAG edge mismatch. execution/reasoning. Ev: `R`.
- **break-filter-js-from-html** (medium) — `task_done`, 5 steps. Failed grading. execution/reasoning. Ev: `R`.
- **build-cython-ext** (medium) — `task_done`, 19 steps. numpy/cython build/runtime mismatch. execution/reasoning. Ev: `R`.
- **build-stp** (easy) — `task_done`, 15 steps. `stp: error while loading shared libraries:
  libstp.so.2.3` → 7 AssertionErrors. Built but library not on loader path. execution/reasoning. Ev: `R`.

---

## VALID RUN, GRADER COULD NOT EXECUTE — verifier_exit = 127 — 2

- **broken-networking** (medium) — `implicit_stop`, 26 steps. Test harness failed to run:
  `/root/.local/bin/env: No such file`, `uv: command not found`, `.tbench-testing/bin/activate:
  No such file`. Agent couldn't `apt`/install (network disabled = the task). Primary:
  verification/grading; contributing environment/runtime. **Outcome not a clean capability fail.** Ev: `R`.
- **broken-python** (easy) — `implicit_stop`, 40 steps. `No module named 'pip'`, then
  `pytest: command not found` (exit 127). Agent tried `ensurepip` (step-39 exit 1) but didn't
  restore pip/pytest the grader needs. Primary: verification/grading. Ev: `R`.

---

## INVALID RUN — not scoreable as capability — 3

- **add-benchmark-lm-eval-harness** — `runner_exception`, `reason=runner_exception`.
  `details.error = ModelClientError('azure openai request failed with status 400')`.
  **provider/model transport.** A rejected request, not a capability fail. Re-run required. Ev: `R`.
- **build-pov-ray** — `runner_exception`. `details.error = PermissionError(13, 'Permission denied')`.
  **environment/runtime** (harness fs permission). Ev: `R`.
- **build-linux-kernel-qemu** — `row_status=invalid_environment`, `reason=docker_build_failed`,
  `docker build … returncode 137` in 5.2 s. **sandbox/container setup.** Ev: `R`,`S`.

---

## VALID RUN, TIMEOUT, NO GRADE — UNCLEAR — 1

- **build-initramfs-qemu** — `rc=143` (SIGTERM) at **2739 s**; 0-byte log; **no `row.json`**.
  Outcome **UNCLEAR** (killed before grading). Primary: timeout/step-budget. Ev: `P`,
  `logs/resume_nohup.log:34-36`, empty `L`.

---

## INVALID LAUNCH (import crash) — Attempt 1 — 216 (grouped)

All 216 Attempt-1 tasks alphabetically after `build-stp` (first = `build-tcc-qemu`).
Identical failure: `ModuleNotFoundError: No module named 'runner'` at
`run_aether2_g3_official.py:30`; `rc=1`, elapsed ≤2 s; no `row.json`. **Never executed.**
Class: environment/runtime (F1). Includes the prediction-named tasks `qemu-startup`,
`extract-moves-from-video`, `install-windows-3.11`, `video-processing` — so none of them produced
authoritative evidence (see `prediction_audit.md`).
Ev: any `logs/attempt_1_<task>_.log` (md5 `d8e4df14…`), `logs/autorestart.log`, `P`.

---

## INVALID LAUNCH (contaminated) — Attempt 2 — 241 (grouped, diagnostic-only)

All 241 Attempt-2 tasks: identical import crash, ran 12:06:24→12:07:13 (≤1 s each), **0 rows**.
Class: environment/runtime + contamination (F1). **Carries no scoring weight.** Usable only as
confirmation that the import defect is deterministic and environment-wide.
Ev: `logs/attempt_2_*.log`, `logs/autorestart.log:463-947`, empty `rows/attempt2_rows_combined.jsonl`.
