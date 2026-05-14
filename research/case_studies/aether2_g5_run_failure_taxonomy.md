# Failure Taxonomy — Causal Families (not error-string groups)

Families are ordered by number of affected attempts. **Family sizes for capability families are
computed only over the 19–24 valid Attempt-1 rows** and are explicitly small-n. Attempt 2 is
never counted toward capability families.

Taxonomy classes used (from the mandated list): environment/runtime, provider/model transport,
sandbox/container setup, tool contract, path/cwd, schema/parsing, evidence acquisition,
reduction/selection, execution/reasoning, process/service/session persistence,
verification/grading, timeout/step-budget, contamination, model capability, unclear.

---

## F1 — Harness launch / import-path collapse  ·  **457 attempts**  ·  confidence HIGH
**Primary class: environment/runtime.** Contributing: process/service/session persistence;
contamination (Attempt 2).

- **Size:** 216 Attempt-1 (every task after `build-stp`) + 241 Attempt-2 = **457 / 482 (94.8%)**.
- **Signature (byte-identical, md5 `d8e4df14…`, 457×):**
  ```
  File ".../tools/run_aether2_g3_official.py", line 30, in <module>
      from runner.aether2.bridge_harbor import TaskSpec, _build_model_client
  ModuleNotFoundError: No module named 'runner'
  ```
- **First material divergence:** process start — crash occurs *before* argparse, Docker, model
  call, or any task work. `progress.tsv` still records `rc=1`, elapsed ≤2 s.
- **Causal mechanism (evidence-chained):**
  1. `resume_full_twice.sh` died at `build-tcc-qemu start 02:12:49`
     (`logs/resume_nohup.log:45` is the last line — no matching `end`).
  2. ~10 h gap, then a **VM reboot ~12:05 UTC** (`FREEZE_MARKER.txt`: `up 9 min` at 12:14:31).
  3. An auto-restart relaunched the tournament at `12:05:34`
     (`logs/autorestart.log:1-4`), skipping the 25 `already done` real runs and racing through
     the remaining 216 Attempt-1 tasks (`12:05:35→12:06:24`) then all 241 Attempt-2 tasks
     (`12:06:24→12:07:13`), each crashing instantly.
  4. The relaunch environment lacked the repo root on `sys.path`/`PYTHONPATH`, and
     `source_snapshot/tools/run_aether2_g3_official.py` performs `from runner.aether2…` at module
     top (lines 30-32) **with no `sys.path.insert` bootstrap** (lines 15-28 are stdlib only).
- **Source mechanism implicated:** `tools/run_aether2_g3_official.py:30-32` (missing path
  self-bootstrap) + the autorestart unit / `resume_full_twice.sh` (does not export `PYTHONPATH`).
- **Competing explanations considered & rejected:**
  - *Disk/Docker exhaustion* (FREEZE_MARKER 80% disk, 16 images): **rejected** — crash is a Python
    import error before Docker is touched; logs show no `no space left on device`.
  - *Deleted `runner/` package*: **rejected** — `runner/__init__.py` present in manifest and
    `source_snapshot/`; the same script imported fine for the 24 real runs.
  - *Code regression in `runner/aether2`*: **rejected** — error is top-level package resolution
    (`No module named 'runner'`), not a sub-module/attribute error.
- **Why this dominates:** it invalidates 89.6% of Attempt 1 and 100% of Attempt 2.
- **Representative attempts:** `build-tcc-qemu` (first crash, A1), `qemu-startup` (A1),
  `extract-moves-from-video` (A1), every Attempt-2 task.
- **Evidence:** `logs/attempt_1_build-tcc-qemu_.log`, `logs/attempt_2_qemu-startup_.log`,
  `logs/resume_nohup.log:34-45`, `logs/autorestart.log:1-60,946-947`, `logs/master.log:148-151`,
  `FREEZE_MARKER.txt`, `source_snapshot/tools/run_aether2_g3_official.py:30-32`.

> Note: F1 is *not* a model-capability or task-difficulty result. Per AGENTS.md ("separate
> environment/tooling failures from capability failures"), it must be repaired before any
> capability rate is trusted.

---

## F2 — False-positive `task_done` (agent declares done; external grader fails) · **10 valid rows** · MEDIUM
**Primary class: execution/reasoning.** Contributing: verification/grading.

- **Size:** 10 / 14 valid `finalize=task_done` Attempt-1 rows failed grading (the other 4 are the
  passes). Among captured fails this is the single largest *capability* pattern.
- **Representative tasks & first divergence:**
  - `aimo-airline-departures` — wrote script in **3 steps**, called `task_done`; 3/4 tests passed,
    `test_answer` AssertionError (wrong numeric answer). Stopped far too early.
  - `amuse-install` — `task_done` after venv created, but `amuse.community` not importable
    (`ModuleNotFoundError`); install incomplete.
  - `build-stp` — `task_done`, but `stp: error while loading shared libraries: libstp.so.2.3`
    (built but library not on loader path) → 7 test AssertionErrors.
- **Common shape:** the agent's own stopping criterion is satisfied while the externally
  observable condition is not; the advisory verifier (F4) fails to catch it.
- **Evidence:** `rows/attempt1_rows_combined.jsonl` (`finalize_reason`, `verifier_stdout_tail`,
  `tool_invocations`) for each named task.

---

## F3 — Step/effort exhaustion → `implicit_stop` without completion · **6 valid rows** · MEDIUM
**Primary class: execution/reasoning ↔ timeout/step-budget (task-dependent).**

- **Size:** 6 valid Attempt-1 rows finalized `implicit_stop` and failed
  (3d-model-format-legacy, accelerate-maximal-square, adaptive-rejection-sampler,
  blind-maze-explorer-algorithm, broken-networking, broken-python).
- **Split:** `3d-model-format-legacy` (25 steps/27 calls, hard) and `adaptive-rejection-sampler`
  (25 steps) look budget-bound; `accelerate-maximal-square` stopped at **6 steps** (algorithmic —
  Numba impl 0.4× speed, failed perf threshold). So this family is **not** uniformly "needs more
  steps"; it mixes budget pressure with genuine task difficulty. Low confidence to act on with n=6.
- **Evidence:** `rows/attempt1_rows_combined.jsonl` per task.

---

## F4 — Advisory verifier over-optimism (false "clean") · **14 valid rows** · MEDIUM-HIGH
**Primary class: verification/grading (advisory layer).**

- **Size:** of 21 rows with an advisory verdict, `verifier_clean=True` on **19**, but only **5**
  actually passed → **14 false "clean" verdicts**. `verifier_clean=False` fired on only 2 rows
  (`blind-maze-explorer-5x5`, `…-algorithm`), both of which did fail.
- **Reading:** the Layer-2 advisory verifier has **~26% precision and very low recall** for real
  failures on this sample. It provides almost no usable promotion/keep signal.
- **Constraint:** advisory output is **not** promotion evidence (AGENTS.md; EVIDENCE RULES §6).
  Disagreement with the external grader is preserved, not reconciled.
- **Evidence:** `loop_result.verifier_clean` vs `row_status` across the 21 rows
  (`scripts/authoritative_attempt1.json`).

---

## F5 — Verifier/test-harness execution failure (exit 127) · **2 valid runs** · MEDIUM
**Primary class: verification/grading.** Contributing: environment/runtime.

- `broken-networking`: test harness `aether2-run-tests.sh` needs `uv`/`/root/.local/bin/env`,
  which are absent (and the task itself disables networking, so the agent cannot `apt`/`uv`
  install) → `uv: command not found`, exit 127.
- `broken-python`: agent (40 steps) could not fully restore `pip`; `pytest: command not found` → 127.
- **Open question:** is exit 127 a legitimate "agent didn't repair env" fail, or a grader-design
  defect (test harness assuming `uv`/network)? Both are plausible; needs the run-tests script
  source (not in bundle) to resolve. Classified `verification/grading` + flagged for diagnosis.
- **Evidence:** `verifier_stderr_tail` for both rows.

---

## F6 — Invalid runs: provider / sandbox / filesystem · **3 attempts** · HIGH
- `add-benchmark-lm-eval-harness` — **provider/model transport**:
  `ModelClientError('azure openai request failed with status 400')`. A 400 is a *rejected request*
  (malformed/oversized/filtered), not a capability fail.
- `build-pov-ray` — **environment/runtime**: `PermissionError(13, 'Permission denied')` in the
  harness (artifact/workspace write).
- `build-linux-kernel-qemu` — **sandbox/container setup**: `docker build … returncode 137` in
  5.2 s (build killed; legacy-builder/buildx warning present).
- **Evidence:** top-level `details` + `reason` fields of the three rows.

---

## F7 — Timeout / step-budget (real run, no grade) · **1 attempt** · HIGH
- `build-initramfs-qemu` — SIGTERM (`rc=143`) at **2739 s**; 0-byte log; no `row.json`
  (killed before grading) → authoritative outcome **UNCLEAR**.
- **Evidence:** `progress.tsv`, `logs/resume_nohup.log:34-36`, empty
  `logs/attempt_1_build-initramfs-qemu_.log`.

---

## Family rollup

| Family | Class (primary) | Attempts | Population | Confidence | Actionable as G5 capability lane? |
|---|---|---:|---|---|---|
| F1 launch/import collapse | environment/runtime | **457** | A1 tail + all A2 | HIGH | **Yes — precondition repair** |
| F2 false-positive task_done | execution/reasoning | 10 | valid A1 | MEDIUM | Not yet (needs valid baseline) |
| F3 step exhaustion / implicit_stop | execution/reasoning | 6 | valid A1 | MEDIUM | Not yet |
| F4 advisory verifier over-optimism | verification/grading | 14 | valid A1 | MED-HIGH | Not yet (advisory ≠ promotion) |
| F5 verifier exec-127 | verification/grading | 2 | valid A1 | MEDIUM | Diagnose grader robustness |
| F6 invalid runs (provider/sandbox/fs) | mixed | 3 | A1 | HIGH | Guardrail, not a lane |
| F7 timeout no-grade | timeout/step-budget | 1 | A1 | HIGH | Guardrail |

**No capability family (F2–F5) has adequate evidence to anchor a mechanism**: each rests on
6–14 rows from a run that is 95% invalid, and the advisory signal (F4) is unreliable. The only
family with decisive evidence and harness-general scope is **F1**. See `g5_lane_recommendation.md`.
