# G5 Lane Recommendation

> G5 (spec §14) = "failure-class iteration loop — one generic mechanism per identified failure
> class, each validated against a held-out homolog; sentinels: qemu-startup green-check, BFCL
> adapter, non-TB generalization board." This document ranks candidate lanes from the frozen
> evidence and selects **exactly one** first lane. It does **not** implement anything.

## Ranking criteria (from ANALYSIS WORKFLOW Phase 5)
affected valid attempts · causal-diagnosis confidence · harness-general vs task-specific ·
existence of a proper eval · expected score gain · regression risk · implementation cost ·
deterministic-grading testability · availability of comparison/sentinel rows.

## Candidate lanes

| Lane | Family | Valid attempts affected | Conf. | Harness-general | Proper eval exists? | Det. grading | Impl. cost | Notes |
|---|---|---:|---|---|---|---|---|---|
| **L1 — Eval-substrate launch integrity + valid n=2 re-baseline** | F1 | **457/482** | **HIGH** | **Yes** | the re-baseline IS the eval | **Yes** (rows produced or not) | **Low** | Precondition for everything |
| L2 — False-positive `task_done` reducer | F2 | 10 | MED | Yes | No | partial | Med | Needs valid baseline first |
| L3 — Advisory-verifier reliability | F4 | 14 | MED-HI | Yes | No | hard | Med-Hi | Advisory ≠ promotion; measure post-baseline |
| L4 — Step/effort budget tuning | F3 | 6 | LOW | partial | No | partial | Low | Confounded with task difficulty |
| L5 — Grader robustness (exit-127 tasks) | F5 | 2 | MED | Yes | No | yes | Low | Small; fold into L1 re-baseline |

## Why L2–L5 are NOT the first lane (evidence-based deferral)
1. **Insufficient valid evidence.** L2–L5 rest on 2–14 rows drawn from a run that is **95%
   invalid**. AGENTS.md: "No new variant without a target eval, predicted delta, and sentinels"
   and "separate environment/tooling failures from capability failures **before** proposing
   architecture changes." Neither is satisfiable until F1 is fixed.
2. **The capability signal itself is currently untrustworthy.** The advisory verifier (F4) is wrong
   on 14/19 "clean" calls, so we cannot even trust the harness's own success signal yet.
3. **No proper homolog eval exists** for F2–F5 (the reset-stage eval substrate is not yet built;
   AGENTS.md "First Reset Goals"). Building a capability mechanism now would violate the eval-first
   rule ("Do not create or promote variants before the relevant eval substrate exists").

## ✅ SELECTED FIRST G5 LANE — **L1: Eval-substrate launch integrity + valid n=2 re-baseline**

**Class:** environment/runtime repair (explicitly allowed without a prior proper eval per AGENTS.md:
"create or choose a proper eval … unless the work is strictly an environment/runtime repair").

**One generic mechanism (G5 form):** make the eval harness *fail loud and early* instead of
silently recording launch crashes as task failures, and make the runner *self-locating* so it
cannot lose its imports across restarts/reboots. Concretely (to be implemented in the NEXT goal,
not here):
- `tools/run_aether2_g3_official.py`: add a `sys.path` self-bootstrap (insert repo root =
  `Path(__file__).resolve().parents[1]`) **before** the `from runner.aether2…` imports.
- `resume_full_twice.sh` / autorestart unit: export `PYTHONPATH=<repo root>`; **abort the whole
  tournament** if the first launch cannot import/build (don't march through 457 tasks writing
  `rc=1`). Treat repeated instant (`elapsed ≤ 2 s`) `rc≠0` as a fatal environment fault.
- Emit an explicit `invalid_launch` / `invalid_environment` row (not a silent `rc=1`) whenever a
  task does not reach the grader, so future scoreboards separate launch faults from capability fails.
- (Secondary) prune Docker images between tasks / add a disk guard (the 80% disk is a latent risk,
  though it was **not** this run's cause).

This is the **G5 form** "one generic mechanism per identified failure class" applied to the
dominant failure class (F1, environment/runtime), and it is the literal precondition for the G5
sentinel `qemu-startup green-check` (which could not run here).

### Mechanism-prerequisite spec (per Phase 5 requirements)

- **Proper targeted eval / diagnostic:** the n=2 full TerminalBench re-baseline itself is the eval;
  add a **launch-integrity diagnostic** = "fraction of attempts that reach the grader." Today this
  is **24/241 (10%)**; target **≥ 95%**.
- **Baseline (authoritative, this bundle):** Attempt 1 valid-scored **5/19 (26.3%)**; reach-grader
  rate **10%**; invalid-launch attempts **457/482**.
- **Known-bad case (deterministic):** relaunch `run_aether2_g3_official.py` from a shell with the
  repo root NOT on `sys.path` → must reproduce `ModuleNotFoundError: No module named 'runner'`
  (the F1 signature). After the fix, the same launch must import cleanly.
- **Ceiling check:** re-running the **25 already-executed Attempt-1 tasks** must reproduce the **5
  known passes** (acl-permissions-inheritance, analyze-access-logs, assign-seats, attention-mil,
  build-pmars) and produce a `row.json` for **every** task (reach-grader = 100% on this subset).
- **Predicted score delta:** reach-grader 10% → ≥95%; invalid-launch rate → ~0%; **capability pass
  rate becomes measurable for the first time** (no numeric capability-gain claim is made — that is
  what the re-baseline measures).
- **Named regression sentinels:** the **5 known passes must still pass** (any regression = stop);
  spec §14 G5 sentinels **`qemu-startup` green-check** + **BFCL/tool-call adapter** + non-TB
  generalization board (`tools/aether2_genericity_check.py` green).
- **Contamination / invalid-run guardrails:** Attempt 1 and Attempt 2 scored separately; any attempt
  that does not reach the grader is emitted as `invalid_launch`/`invalid_environment` and **excluded
  from pass-rate denominators**; abort-on-mass-instant-failure prevents a poisoned restart from
  "completing" the tournament.
- **Stop / kill criteria:** stop if (a) the import fix does not eliminate the F1 signature in the
  known-bad reproduction; (b) any of the 5 known passes regresses; (c) reach-grader stays <95% for
  a non-F1 reason → open a narrower diagnostic instead of widening scope.
- **A-only / B-only / A+B (interaction):** two related fixes exist — **A** = `sys.path` self-bootstrap
  in the runner; **B** = `PYTHONPATH`/fail-fast in the launcher+autorestart. Test **A-only**
  (launcher still broken, runner self-heals), **B-only** (runner unchanged, launcher exports path),
  and **A+B**; promote the combination that gives reach-grader ≥95% with no sentinel regression.
  Expectation: A is sufficient for correctness; B adds defense-in-depth + honest invalid rows.

### Confidence & competing-explanation note
HIGH. F1 is evidenced by 457 byte-identical crash logs, a reboot fingerprint, the orchestration
timeline, and the source defect. The disk-exhaustion alternative was considered and falsified.
The only residual uncertainty is the *exact* missing launch-env detail (PYTHONPATH vs venv vs cwd),
which the chosen fix (self-bootstrap) resolves regardless.

## What this lane is NOT
It is not a model-facing mechanism, not a prompt tweak, not a capability claim, and not a promotion.
It restores measurement validity so that L2–L5 can later be opened **with** a proper eval, a
baseline, and sentinels — as the eval-first reset requires.
