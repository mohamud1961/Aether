# Outcome Scoreboard — Reconstructed from Authoritative Evidence

Every number below is reproducible from `normalized_attempt_rows.jsonl`
(`scripts/build_normalized_rows.py`). **Attempt 1 and Attempt 2 are scored as
separate populations and are never merged** (ATTEMPT SEPARATION).

---

## A. Attempt 1 — the valid scoring population (n = 241 attempts)

### A.1 Validity classification (denominator = 241)

| validity_status | n | meaning |
|---|---:|---|
| `INVALID_LAUNCH` | **216** | `import runner` crash after reboot; never ran (env/runtime) |
| `VALID_SCORED` | **19** | verifier ran, produced exit 0/1 → 5 pass + 14 fail |
| `INVALID_RUN` | 3 | provider 400 / PermissionError / docker-build-fail before grading |
| `VALID_RUN_GRADER_EXEC_FAIL` | 2 | verifier exit 127 (test harness couldn't execute) |
| `VALID_RUN_TIMEOUT` | 1 | `build-initramfs-qemu` SIGTERM @2739 s, no grader row |
| **Authoritative rows captured** | **24** | = 19 VALID_SCORED + 3 INVALID_RUN + 2 exec-127 |

So **only ~25/241 (10.4%) Attempt-1 attempts executed for real**; 216/241 (89.6%) are
environment-collapse artifacts carrying **no** capability signal.

### A.2 Authoritative passes (n = 5) — verifier_exit_code = 0, row_status = pass

| task_id | difficulty | category | finalize | wall_s | progress_rc |
|---|---|---|---|---:|---:|
| acl-permissions-inheritance | medium | system-administration | task_done | 46.4 | 0 |
| analyze-access-logs | easy | data-science | implicit_stop | 28.5 | 0 |
| assign-seats | easy | algorithms | task_done | 30.9 | 0 |
| attention-mil | medium | model-training | task_done | 175.4 | 0 |
| build-pmars | medium | software-engineering | task_done | 196.5 | 0 |

Triangulated three independent ways (combined `row.json` + per-task `scoreboards/*.md` +
`progress.tsv` `rc=0`). `rc=0 set == row_status=pass set` exactly. **No passes exist outside the
24 captured rows** (only 5 `rc=0` rows exist in all of Attempt 1, and all 5 are captured).

### A.3 Pass rates — reported with EVERY denominator (QUALITY BAR)

| Denominator | Definition | Rate |
|---|---|---|
| All-attempt (naïve) | 5 / 241 | **2.07%** ← matches `score_summary.txt`, but **misleading**: 216 are launch crashes |
| Captured rows | 5 / 24 | 20.83% |
| Valid runs (scored + exec-127) | 5 / 21 | 23.81% |
| **Valid-scored (verifier gave 0/1)** | **5 / 19** | **26.32%** |
| True full-population capability rate | 5 / (unknown valid n) | **`INSUFFICIENT_EVIDENCE`** |

> The honest headline is **not** "2.07%." It is: *on the 19 Attempt-1 tasks where the harness
> actually executed a task and the grader returned a verdict, 5 passed (26.3%); the remaining
> 216 tasks never ran.* The full-241 capability rate is unknown and unrecoverable from this bundle.

### A.4 Authoritative failures that ARE valid capability/harness signal (n = 14, verifier_exit=1)

3d-model-format-legacy, accelerate-maximal-square, adaptive-rejection-sampler,
aimo-airline-departures, amuse-install, ancient-puzzle, audio-synth-stft-peaks,
bank-trans-filter, blind-maze-explorer-5x5, blind-maze-explorer-algorithm, bn-fit-modify,
break-filter-js-from-html, build-cython-ext, build-stp. (Per-task diagnosis in `task_findings.md`.)

### A.5 Attempt-1 attempts that are NOT capability signal (must not be scored as fails)

| task_id | class | evidence |
|---|---|---|
| add-benchmark-lm-eval-harness | provider/model transport | `ModelClientError('azure openai request failed with status 400')` |
| build-pov-ray | environment/runtime | `PermissionError(13, 'Permission denied')` |
| build-linux-kernel-qemu | sandbox/container setup | `docker build … returncode 137` in 5.2 s |
| broken-networking | verification/grading (+env) | verifier exit 127: `uv: command not found`, `/root/.local/bin/env: No such file` |
| broken-python | verification/grading (+env) | verifier exit 127: `No module named 'pip'`, `pytest: command not found` |
| build-initramfs-qemu | timeout/step-budget | SIGTERM @2739 s, no grader row → outcome UNCLEAR |
| (216 tasks) | environment/runtime | identical `ModuleNotFoundError: No module named 'runner'` |

---

## B. Attempt 2 — CONTAMINATED, NOT SCOREABLE (n = 241 attempts)

| metric | value |
|---|---|
| authoritative rows | **0 / 241** (`attempt2_rows_combined.jsonl` is 0 bytes) |
| real executions | **0** |
| passes | **0** (cannot be asserted as fails either — they never ran) |
| validity_status | `INVALID_LAUNCH_CONTAMINATED` ×241 |
| runtime | all ≤1 s (200×0 s, 41×1 s); whole attempt ran 12:06:24→12:07:13 (49 s) |
| contamination mechanism | ran **entirely** in the post-reboot broken-`sys.path` env; every task died at `import runner` |

**Attempt 2 contributes zero pass/fail/score evidence.** It is retained only as diagnostic
confirmation that the import defect is environment-wide and deterministic (see `failure_taxonomy.md` F1).

---

## C. Cross-attempt reconciliation

- **Agreeing across attempts:** both attempts show the same 457-launch import-crash signature for
  every task that ran post-reboot — confirming the defect is environmental, not task-specific.
- **Unique to Attempt 2:** nothing usable for scoring. Every Attempt-2 row is contaminated.
- **`score_summary.txt`** ("Attempt 1: 5/241; Attempt 2: 0/241") is *arithmetically* consistent
  with `progress.tsv` `rc=0` counts, but it silently treats 216 launch crashes + 1 timeout as
  "failed" and is therefore **not** a valid capability scoreboard. Not used as authority.

## D. Uncertainty ledger

| Claim | Confidence | Basis |
|---|---|---|
| 5 authoritative Attempt-1 passes (named) | **HIGH** | rows + scoreboards + progress, triangulated |
| 216 Attempt-1 + 241 Attempt-2 are invalid launches | **HIGH** | 457 byte-identical crash logs + timeline |
| Valid-scored pass rate 5/19 | **HIGH** (for that sub-pop) | direct grader verdicts |
| True 241-task capability rate | **INSUFFICIENT_EVIDENCE** | 216/241 never ran |
| Attempt-2 outcomes | **N/A — contaminated** | 0 rows, uniform import crash |
| Per-task failure *class* for the 14 valid fails | MEDIUM | verifier tails + trajectories, small n |
