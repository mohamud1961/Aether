# Prediction Audit — Pre-registered Predictions (`AETHER2_BUILD_SPEC.md` §15)

Audited strictly against authoritative evidence **present in this bundle**. Where the named task
landed in the F1 import-crash region (and thus never ran), the prediction is reported as
`INSUFFICIENT_EVIDENCE` — **not** silently reinterpreted (EVIDENCE RULES §5, AGENTS.md "do not
reinterpret failed predictions as successes").

| # | Prediction | Predicted | Observed (authoritative) | Verdict | Keep active? |
|---|---|---|---|---|---|
| 1 | `qemu-startup` PASS in ≤12 model calls | pass, ≤12 calls | A1 = `INVALID_LAUNCH` (import crash, 0 s, no row); not bundled in G3 calib | **INSUFFICIENT_EVIDENCE** | Yes — unresolved |
| 2 | `extract-moves-from-video` flip 0→1 | pass | A1 = `INVALID_LAUNCH` (import crash, no row) | **INSUFFICIENT_EVIDENCE** | Yes — unresolved |
| 3 | `install-windows-3.11` flip 0→1 | pass | A1 = `INVALID_LAUNCH` (import crash, no row) | **INSUFFICIENT_EVIDENCE** | Yes — unresolved |
| 4 | `video-processing` — NO prediction, diagnose first | (none) | A1 = `INVALID_LAUNCH` (import crash, no row) | **NOT DIAGNOSABLE here** | Yes — still needs diagnosis |
| 5a | Cache-hit ratio ≥ 80% | ≥80% | pooled **88.4%**; 13/21 rows ≥80% | **SUPPORTED (pooled)**, mixed per-task | Yes — refine |
| 5b | ≤150k fresh input tokens per hard task | ≤150k | hard tasks: 3d-model **61,499**; bn-fit-modify **17,806** | **SUPPORTED** (n=2) | Yes |

## Details & causal explanation

### Predictions 1–3 (the three flagship hard-task flips) — INSUFFICIENT_EVIDENCE
- `qemu-startup`, `extract-moves-from-video`, `install-windows-3.11` are all alphabetically after
  `build-stp`, so in the **F1 import-crash tail**: `progress.tsv` `rc=1`, elapsed 0 s, **no
  `row.json`** (`scripts/build_normalized_rows.py` output confirms `validity=INVALID_LAUNCH`).
- The `file_manifest.txt` references **G3-calibration** `row.json` for these tasks
  (`aether2_g3_calibration/…/{qemu-startup,extract-moves-from-video,install-windows-3.11}/row.json`),
  but **that content is not in the bundle** (no `aether2_g3_calibration/` tree; `find` returns
  nothing; `grep` of `rows/` returns nothing).
- **Causal explanation:** the run never reached these tasks with a working harness; the predictions
  are neither confirmed nor refuted. They **remain active** and unresolved.
- **Do not** infer pass/fail from `score_summary.txt` (which buckets them as "failed" via `rc=1`).

### Prediction 4 (`video-processing`) — NOT DIAGNOSABLE here
- Spec asked to diagnose before predicting (a prior environment-setup pause was flagged).
- `video-processing` is also in the F1 tail (no row). No diagnostic evidence in this bundle.

### Prediction 5 (cache ratio & fresh-token budget) — SUPPORTED, with scope caveats
- Computed over the **21 captured Attempt-1 rows that ran the loop** (`tokens_cached`/`tokens_fresh`):
  - **Pooled cache-hit ratio = 4,090,752 / 4,629,023 = 88.4%** → meets ≥80%.
  - Per-task: **13/21 rows ≥80%.** The 8 below 80% are all short/easy tasks with tiny absolute
    token counts (e.g., `aimo-airline-departures` 53.4% at 5,128 fresh; `bank-trans-filter` 54.3%),
    where there is little transcript to amortize the cached prefix over. The prediction holds for
    substantive tasks and in aggregate; it is **not** uniformly true on trivial tasks.
  - Hard-task fresh tokens both well under the 150k budget (61,499 and 17,806).
- **Important scope caveat:** Prediction 5 was *intended* to be validated on hard tasks like the
  three flagship flips — **none of which ran**. The support here comes from a different, mostly
  easy/medium task set. So 5 is **SUPPORTED on available evidence** but **not** on the originally
  intended hard-task population.

## Net

- **0 of 4 task-outcome predictions (1–4) can be resolved by this bundle.** The full tournament
  never validly reached any flagship predicted task.
- **Prediction 5 is the only one with authoritative support**, and only on an unintended (easier)
  task subset.
- **No prediction is refuted; none is confirmed for the flagship tasks.** A valid re-baseline (G5
  lane below) is required to settle predictions 1–4.
