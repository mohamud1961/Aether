# Evidence Inventory & Integrity Assessment

**Bundle analyzed (immutable):**
`tracking/collab/vm_pulls/tracking/collab/aether2_g5_failure_analysis_clean_20260613T121431Z`

**Provenance (`FREEZE_MARKER.txt`):** frozen `Sat Jun 13 12:14:31 UTC 2026` on `harnesseng-dev`
(Azure VM), `FULL_ROOT=tracking/collab/aether2_full_tournament/full_twice_20260612T200830Z`.
The freeze marker is treated as **provenance only**, not proof of completeness (per EVIDENCE RULES §8).

> **Two FREEZE_MARKER facts that turned out to be load-bearing:** `up 9 min` (the VM had
> been up only ~9 minutes at freeze) and disk `/dev/root 49G/61G 80%`. The uptime is the
> fingerprint of the reboot that produced the contamination (see root cause). The disk figure
> was an early red-herring (a disk-exhaustion hypothesis was raised and **falsified** by logs).

## 1. File-type inventory (what physically exists in the bundle)

| Evidence type | Path | Count / size | Status |
|---|---|---|---|
| Freeze/provenance | `FREEZE_MARKER.txt` | 690 B | present |
| Run orchestrator | `resume_full_twice.sh` | 2.4 KB | present |
| Progress table | `progress.tsv` | 482 rows | present, complete (1 row/attempt/task) |
| Summary (non-authoritative) | `score_summary.txt` | — | present; **not trusted** per rules |
| Authoritative rows — Attempt 1 | `rows/attempt1_rows_combined.jsonl` | **24** `### FILE:` blocks | **partial (24/241)** |
| Authoritative rows — Attempt 2 | `rows/attempt2_rows_combined.jsonl` | **0 B** | **empty (0/241)** |
| Per-task scoreboards | `scoreboards/*.md` | 24 (all `attempt_1`), 0 `attempt_2` | corroborate the 24 rows |
| Per-task logs | `logs/attempt_{1,2}_*.log` | 241 + 241 = 482 | present (thin wrappers) |
| Orchestration logs | `logs/{master,autorestart,resume_nohup}.log` | 3 | present |
| Error index | `error_grep.txt` | 2245 lines | present; **index only**, not authority |
| File manifest | `file_manifest.txt` | 1717 paths | present (VM-side listing) |
| Source snapshot | `source_snapshot/{runner,tools,tests}` | runner/aether2 (18 .py) + 3 tools + tests | present |

The combined "jsonl" is **not** valid JSONL — it is a concatenation of pretty-printed
`row.json` files separated by `### FILE: <path>` markers. Parsed accordingly
(`scripts/parse_rows.py`).

## 2. Manifest coverage vs. files actually present

- `file_manifest.txt` references **31** `row.json` paths: **24 under `attempt_1/`, 0 under
  `attempt_2/`**, and **7 under `aether2_g3_calibration/`** (qemu-startup, extract-moves-from-video,
  fibonacci-server, accelerate-maximal-square×2, qemu-startup×2, install-windows-3.11).
- The manifest lists **26 distinct `attempt_1` task directories and 0 `attempt_2` directories**.
- The **7 G3-calibration `row.json` are referenced in the manifest but their CONTENT is NOT in
  the bundle** (no `aether2_g3_calibration/` tree present; verified by `find`). They are
  therefore unusable as authoritative evidence here.
- Net: the manifest **confirms** that only 24 Attempt-1 result rows and **zero** Attempt-2 result
  rows ever existed in `FULL_ROOT`. The 24/241 gap is a real artifact of the run, not a
  bundling omission.

## 3. Truncated / empty / duplicate / malformed detection

- **457 of 482 per-task logs are byte-identical** (md5 `d8e4df14…`): a 5-line Python traceback
  `ModuleNotFoundError: No module named 'runner'` at `tools/run_aether2_g3_official.py:30`.
  Split: **216 Attempt-1 + 241 Attempt-2**.
- **24 Attempt-1 logs are unique** (`Wrote …/result_rows.jsonl` + `…/scoreboard.md`) — the real runs.
- **1 Attempt-1 log is empty (0 B):** `build-initramfs-qemu` (the SIGTERM timeout).
- Accounting: 24 real + 1 empty + 457 crash = 482. ✓ No truncated/partial logs beyond these classes.
- `attempt2_rows_combined.jsonl` is **legitimately empty** (Attempt 2 produced no rows), not truncated.

## 4. Task IDs and attempts reconstructed

- **241 distinct task IDs**, identical set across both attempts (verified).
- **482 attempts** total (Attempt 1 + Attempt 2), one `progress.tsv` row each.
- `progress.tsv` columns (from `resume_full_twice.sh:62`): `attempt, task_id, rc, elapsed_sec, date_utc`.

## 5. Per-evidence availability matrix

Legend: ✅ present & authoritative · 🟡 partial/derived · ❌ absent · ⛔ contaminated

| Required evidence (EVIDENCE RULES §3) | Attempt 1 | Attempt 2 |
|---|---|---|
| total task count | ✅ 241 | ✅ 241 |
| attempt count per task | ✅ 1 | ✅ 1 |
| pass/fail reward (authoritative) | 🟡 **24/241** rows (`row_status`,`verifier_exit_code`) | ❌ 0/241 |
| `loop_result.grader_reward` | ❌ **null in all 24** (field never populated) | ❌ |
| contamination state | ✅ derivable (logs+timeline) | ⛔ 241/241 contaminated |
| timeout / runtime | ✅ `progress.tsv` elapsed (all 482) | ✅ (all ≤1 s) |
| model & route | 🟡 implied GPT-5.4-mini Azure (spec §14); per-row route field absent | ❌ |
| verifier/grader result | 🟡 24/241 (`verifier_exit_code`,`verifier_stdout/stderr_tail`) | ❌ 0/241 |
| advisory verifier (`verifier_clean`,`discrepancy_reports`) | 🟡 21/241 (loop ran) | ❌ |
| trajectory / tool-event reconstruction | 🟡 21/241 (full `tool_invocations` w/ envelopes) | ❌ |
| tokens (fresh/cached) | 🟡 21/241 | ❌ |
| cost | ❌ `cost=0.0` placeholder in all rows | ❌ |

## 6. Authoritative-field map (what is and isn't trustworthy in a row)

- **AUTHORITATIVE external grader** = top-level `row_status` ∈ {pass, fail, invalid_environment}
  + `verifier_exit_code` (0 pass / 1 fail / 127 test-exec-failure / null when no grading) +
  `reason` (runner_exception | docker_build_failed) + `verifier_stdout_tail` / `verifier_stderr_tail`.
  Triangulated three ways: combined `row.json`, per-task `scoreboards/*.md`, and `progress.tsv` `rc`
  (`rc=0 ⇔ row_status=pass` — exact match on all 5 passes; `rc=1` = any non-pass; `rc=143` = SIGTERM).
- **ADVISORY verifier** = `loop_result.verifier_clean` (bool) + `loop_result.discrepancy_reports`
  (fresh-context Layer-2). Advisory only; preserved separately (EVIDENCE RULES §6).
- **`loop_result.grader_reward` is `null` in every captured row** — do **not** use it; it is not
  the grader signal in this runner build.

## 7. Integrity verdict (report BEFORE capability analysis — ANALYSIS WORKFLOW Phase 1)

1. **Authoritative grader coverage is 24/241 (10%) for Attempt 1 and 0/241 (0%) for Attempt 2.**
2. **Only ~25 Attempt-1 tasks ever executed for real** (24 graded + 1 timeout). The other
   **216 Attempt-1 + 241 Attempt-2 = 457 attempts never ran** — they crashed at Python import
   before any task work (root cause below).
3. **The bundle does NOT support a 241-task capability scoreboard.** It supports an authoritative
   read on **24 Attempt-1 tasks** plus a high-confidence **run-validity / harness-integrity**
   diagnosis.
4. **Attempt 2 is uniformly contaminated** and carries zero scoring weight.
5. Therefore, per EVIDENCE RULES §4, every full-population capability rate is
   `INSUFFICIENT_EVIDENCE`; only the 24-row sub-population yields authoritative outcomes.

**Root cause of the 457 missing/invalid runs (HIGH confidence — see `failure_taxonomy.md` F1):**
A VM reboot at ~12:05 UTC (FREEZE_MARKER `up 9 min`) triggered an auto-restart
(`autorestart.log` begins `12:05:34`) of `resume_full_twice.sh` in an environment without the
repo root on `sys.path`/`PYTHONPATH`. `tools/run_aether2_g3_official.py:30` imports
`runner.aether2.*` at module top with **no `sys.path` bootstrap**, so every remaining launch died
instantly with `ModuleNotFoundError: No module named 'runner'`, recording `rc=1` in `progress.tsv`
while doing zero work.
