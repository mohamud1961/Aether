# Aether-2 G5 Run-Analysis — Frozen Full-Tournament Evidence

**Analysis date:** 2026-06-13 · **Status:** `READY_FOR_BOUNDED` · **Review gate:** `adversarial_only`

## Goal (as executed)

**Objective:** Analyze the frozen Aether-2 full-tournament evidence, establish trustworthy scored
outcomes and failure classifications, identify the highest-value eval-governed G5 failure lane,
and produce an evidence-backed recommendation without implementing a mechanism or starting another
run. **No token budget.**

**In scope:** reconstruct run population; classify validity/pass/fail/invalid/unclear; separate
harness/model failures from environment/provider/grader/setup/timeout/capture failures; select one
bounded G5 lane; analysis & recommendations only; analysis scripts/outputs outside the frozen folder.
**Out of scope:** editing `runner/aether2/`; implementing mechanisms/variants; rerunning
TerminalBench/Harbor/model/Docker/VM; promoting/rejecting from log impressions; inferring grader
outcomes when authoritative rows are absent; broad multi-mechanism passes.

## Evidence source (immutable)

`tracking/collab/vm_pulls/tracking/collab/aether2_g5_failure_analysis_clean_20260613T121431Z`
— frozen 2026-06-13 12:14:31 UTC from VM `harnesseng-dev`,
`FULL_ROOT=…/aether2_full_tournament/full_twice_20260612T200830Z` (the spec §14 **G4 n=2 baseline**).
Treated as read-only; not modified.

## Methodology

1. Read AGENTS.md, build-spec G5/§13/§15/§16, FREEZE_MARKER, manifest, error_grep, and the actual
   rows/logs/scoreboards/source-snapshot.
2. **Trusted no summaries/filenames.** Parsed the concatenated `row.json` blocks; identified the
   authoritative grader field (`row_status`/`verifier_exit_code`, not the always-null
   `loop_result.grader_reward`); triangulated against per-task scoreboards and `progress.tsv` `rc`.
3. Built `normalized_attempt_rows.jsonl` (one row per 482 attempts) as the single source of truth;
   every aggregate is reproducible from it via `scripts/build_normalized_rows.py`.
4. Classified each attempt into the mandated taxonomy; separated Attempt 1 (scoring) from Attempt 2
   (contaminated); verified the dominant crash from raw logs (not error_grep).
5. Audited the §15 predictions against authoritative evidence only.
6. Ran an adversarial closeout (below).

## Result summary (the headline)

**This is not a capability result — it is a run-validity failure.** The "full tournament n=2" never
validly completed:

- **Only ~25 / 241 Attempt-1 tasks ever executed for real** (24 with authoritative grader rows + 1
  timeout). **216 Attempt-1 + 241 Attempt-2 = 457 / 482 attempts (94.8%) never ran** — they crashed
  at Python import (`ModuleNotFoundError: No module named 'runner'`) after a **VM reboot ~12:05 UTC**
  triggered an auto-restart in an environment without the repo root on `sys.path`.
- **Authoritative Attempt-1 passes: 5** — acl-permissions-inheritance, analyze-access-logs,
  assign-seats, attention-mil, build-pmars (verifier_exit_code=0, triangulated).
- **Pass rates (always with denominator):** valid-scored **5/19 = 26.3%**; captured-rows 5/24 =
  20.8%; naïve all-attempt 5/241 = 2.07% (**misleading** — dominated by launch crashes). True
  241-task capability rate = **INSUFFICIENT_EVIDENCE**.
- **Attempt 2: 0/241, fully contaminated** (ran entirely in the broken-import environment); zero
  scoring weight.
- **Predictions:** 1–4 (qemu-startup, extract-moves-from-video, install-windows-3.11,
  video-processing) all landed in the import-crash tail → **INSUFFICIENT_EVIDENCE / not resolvable**;
  prediction 5 (cache ratio ≥80%; ≤150k fresh/hard) **SUPPORTED** (pooled 88.4%; hard tasks 61k/18k)
  but only on an unintended easier subset.
- **Selected first G5 lane: L1 — eval-substrate launch integrity + valid n=2 re-baseline**
  (environment/runtime repair; precondition for all capability lanes). Capability families
  (false-positive `task_done`, advisory-verifier over-optimism, step budget) are real but rest on
  6–14 rows of a 95%-invalid run and are deferred until a valid baseline + proper evals exist.

## Files in this folder

| File | Purpose |
|---|---|
| `README.md` | this overview + adversarial closeout |
| `evidence_inventory.md` | completeness/integrity matrix + integrity verdict |
| `normalized_attempt_rows.jsonl` | **482 rows**, one per attempt — source of truth |
| `outcome_scoreboard.md` | authoritative totals, validity counts, pass rates, uncertainty |
| `failure_taxonomy.md` | causal families F1–F7, counts, representatives, citations |
| `task_findings.md` | per-task atlas for every failure/invalid/unclear attempt |
| `prediction_audit.md` | §15 predictions vs authoritative evidence |
| `g5_lane_recommendation.md` | ranked lanes + the one selected lane + prerequisite spec |
| `next_goal_prompt.md` | ready-to-use bounded Goal prompt |
| `analysis_manifest.json` | inputs, outputs, counts, timestamps, limitations |
| `scripts/` | read-only parsers/generators (reproduce every number) |

---

## Adversarial closeout (attempting to disprove each material finding)

**Bundle completeness.** *Claim:* only 24 A1 / 0 A2 authoritative rows exist. *Attack:* maybe rows
exist on the VM but weren't bundled. *Rebuttal:* `file_manifest.txt` (the VM-side listing) itself
references only 24 `attempt_1` and 0 `attempt_2` `row.json`; the gap is intrinsic, not a copy
omission. The 7 G3-calibration rows it lists are absent from the bundle → flagged
INSUFFICIENT_EVIDENCE, not used. **Holds.**

**Reconstructed scores.** *Claim:* 5 A1 passes. *Attack:* `loop_result.grader_reward` is null
everywhere — maybe passes are mis-derived. *Rebuttal:* passes come from top-level `row_status=pass`
+ `verifier_exit_code=0`, triangulated against per-task `scoreboards/*.md` and `progress.tsv`
(`rc=0 set == pass set`, exactly 5, all captured). No pass can hide in the tail (only 5 `rc=0` rows
exist in all of A1). **Holds.**

**Top failure-family ranking (F1).** *Attack:* could the 457 crashes be disk/Docker exhaustion
(disk 80%, 16 images)? *Rebuttal:* all 457 logs are byte-identical Python import tracebacks that
fire *before* Docker; no `no space left on device` anywhere; `build-linux-kernel-qemu`'s docker
failure is a *separate*, single real-run event. Disk hypothesis **falsified**. **Holds.**

**Causal attribution (reboot + lost sys.path).** *Attack:* maybe `runner/` was deleted or
`runner/aether2` regressed. *Rebuttal:* `runner/__init__.py` present in manifest + snapshot; same
script imported fine for 24 runs; error is top-level package resolution, not a sub-module/attribute
error; `run_aether2_g3_official.py:30-32` has no `sys.path` bootstrap; `FREEZE_MARKER` `up 9 min` +
`autorestart.log` `12:05:34` fix the reboot. The one residual unknown (exact missing env var) does
not change the fix. **Holds (with that caveat stated).**

**Proposed first lane (L1).** *Attack:* shouldn't G5 pick a capability mechanism? *Rebuttal:*
AGENTS.md forbids capability variants without a proper eval + baseline + sentinels and requires
separating environment from capability first; 95% of the run is invalid and the advisory signal is
unreliable, so no capability lane is presently measurable. L1 is the precondition. **Holds.**

**Prediction conclusions.** *Attack:* `score_summary.txt` implies qemu-startup etc. "failed."
*Rebuttal:* those tasks are import crashes (rc=1, 0 s, no row); calling them "failed" conflates
launch crash with capability. Reported INSUFFICIENT_EVIDENCE, not refuted. **Holds.**

**Unresolved (left explicit):** (a) exact launch-env detail that broke `import runner`; (b) whether
F5 exit-127 is agent fault or grader-design fault (needs the run-tests script, not in bundle);
(c) the true 241-task capability rate — unrecoverable from this bundle, requires the L1 re-baseline.

## Operational state
No mechanism implemented. No run/rerun started. No TerminalBench/Harbor/model/Docker/VM job
launched. No process, container, or VM left running by this analysis (read-only on a local frozen
copy; the source VM's state is whatever the freeze captured and is out of this analysis's control).
