# Variant / Mechanism Hypothesis Backlog

Reset-stage backlog (AGENTS.md §"Eval-First Reset Rules"). Candidates here are **hypotheses**, not
promotions. Per the experiment-discipline rules, no entry may be implemented as a variant without a
target eval, a predicted score delta, and named regression sentinels. Items are marked:

- `EVIDENCE-BACKED / ACTIONABLE` — has decisive evidence and may proceed as a bounded Goal.
- `UNVALIDATED / GATED` — observed but resting on insufficient/contaminated evidence; **must not**
  be implemented until a valid baseline + proper eval exist. No promotion implied.

---

## 2026-06-13 — entries from G5 run-analysis of `full_twice_20260612T200830Z`
Source analysis: `tracking/collab/aether2_g5_run_analysis_20260613/` (24/241 authoritative A1 rows,
0/241 A2 rows; 457/482 attempts invalid launches). Read that before acting on anything below.

### H1 — Eval-substrate launch integrity (self-bootstrapping import + fail-fast) — `EVIDENCE-BACKED / ACTIONABLE`
- **Class:** environment/runtime repair (not a model-facing mechanism).
- **Evidence:** 457 byte-identical `ModuleNotFoundError: No module named 'runner'` crashes at
  `tools/run_aether2_g3_official.py:30` after the ~12:05 reboot autorestart; script has no
  `sys.path` bootstrap (`source_snapshot/tools/run_aether2_g3_official.py:30-32`). Confidence HIGH.
- **Proposed mechanism:** insert repo root into `sys.path` before the `runner.aether2` imports;
  export `PYTHONPATH` in launcher/autorestart; abort tournament on mass instant-launch faults;
  emit explicit `invalid_launch` rows instead of silent `rc=1`.
- **Target eval:** the n=2 re-baseline; diagnostic = reach-grader rate (now 24/241=10% → target ≥95%).
- **Predicted delta:** invalid-launch rate → ~0%; capability rate becomes measurable.
- **Sentinels:** the 5 known passes (acl-permissions-inheritance, analyze-access-logs, assign-seats,
  attention-mil, build-pmars); spec §14 G5 sentinels (qemu-startup green-check, BFCL adapter,
  `tools/aether2_genericity_check.py`).
- **Next Goal:** `tracking/collab/aether2_g5_run_analysis_20260613/next_goal_prompt.md`.

### H2 — False-positive `task_done` reducer — `UNVALIDATED / GATED`
- **Observation:** 10/14 valid `finalize=task_done` Attempt-1 rows failed the external grader
  (agent declared done while the observable condition was unmet; e.g. `aimo-airline-departures`
  stopped at 3 steps with a wrong answer; `build-stp` missed `libstp.so.2.3` on the loader path).
- **Why gated:** n=10 on a 95%-invalid run; no proper homolog eval; advisory verifier (H4) too
  unreliable to use as the closeout check. Needs valid baseline + a `task_done`-discipline eval
  with deterministic grading before any mechanism. **No promotion implied.**

### H3 — Step/effort-budget tuning for `implicit_stop` non-completions — `UNVALIDATED / GATED`
- **Observation:** 6 valid rows finalized `implicit_stop` without completing; but the family mixes
  budget pressure (`3d-model-format-legacy` 25 steps) with genuine algorithmic shortfall
  (`accelerate-maximal-square` stopped at 6 steps, perf threshold missed). Confounded.
- **Why gated:** cannot separate budget from capability with n=6; needs a valid baseline and a
  budget-controlled eval.

### H4 — Advisory-verifier reliability — `UNVALIDATED / GATED (diagnostic first)`
- **Observation:** `loop_result.verifier_clean=True` on 19 rows but only 5 passed → 14 false
  "clean" verdicts (~26% precision, low recall). The Layer-2 advisory verifier provides almost no
  usable signal on this sample.
- **Why gated:** advisory output is explicitly **not** promotion evidence (AGENTS.md); this is a
  measurement-quality concern. Diagnose against a valid baseline before changing the verifier.

### H5 — Grader/test-harness robustness on environment-restricted tasks — `UNVALIDATED / GATED (diagnostic first)`
- **Observation:** `broken-networking` and `broken-python` returned verifier exit 127 because
  `aether2-run-tests.sh` needs `uv`/`pip`/`pytest`/network that those tasks deny. Ambiguous: agent
  fault vs grader-design assumption.
- **Why gated:** resolving requires the run-tests script source (not in the frozen bundle). Open a
  narrow diagnostic; do not assume a mechanism.

### Guardrails (not lanes) — record only
- Provider 400 (`add-benchmark-lm-eval-harness`: `ModelClientError … status 400`) and harness
  `PermissionError`/`docker build rc137` must be emitted as `invalid_run`, never counted as
  capability fails. Latent disk risk (80% at freeze) — add image prune/disk guard with H1.

---

## 2026-06-14 — fake-progress implementation program

Source diagnosis:
`tracking/collab/aether2_fake_progress_analysis_20260614/older_vm_and_trace_rerun_fake_progress_analysis_20260614.md`

Implementation plan:
`tracking/collab/aether2_fake_progress_implementation_plan_20260614/IMPLEMENTATION_FIX_PLAN.md`

### H6 — Activity/evidence separation and evidence provenance — `EVIDENCE-BACKED / ACTIONABLE AFTER EVAL BASELINE`
- **Class:** pre-verifier harness-control failure.
- **Evidence:** traced `gcode-to-text` runs and older false-clean rows show model-authored output writes,
  readbacks, same-method checks, and self-clients being treated as progress/evidence.
- **Proposed mechanism:** separate activity refs from requirement evidence; attach provenance and
  independence facts; make semantic progress depend on a new relevant evidence version.
- **Target eval:** candidate-label, circular recovery, external service protocol, and final-state
  homolog smoke rows plus the staged 13-task diagnostic board.
- **Predicted delta:** at least 60% reduction in premature completion and +1 to +3 task passes.
- **Sentinels:** db-wal-recovery, compile-compcert, prove-plus-comm, BFCL tool schema, simple file task.

### H7 — Evidence-strength-aware verifier cleanliness — `EVIDENCE-BACKED / ACTIONABLE AFTER EVAL BASELINE`
- **Class:** verifier false-clean failure.
- **Evidence:** five scoreable older rows were `verifier_clean=true` but grader-failed; current
  verifier computes strength while clean status considers only satisfied/unresolved verdict.
- **Proposed mechanism:** weak satisfied evidence remains unresolved reflection; clean requires
  requirement coverage with independent strong or non-dominantly-weak evidence.
- **Target eval:** shape-only, proxy-constraint, exact-schema, circular-check, and service-protocol
  homologs.
- **Predicted delta:** clean precision above 90% and +1 to +4 repaired task passes.
- **Sentinels:** clean provided-test fixture, formal proof task, evidence-first recovery pass.

### H8 — EnvContract v2 and attributable runtime monitoring — `EVIDENCE-BACKED / ACTIONABLE AFTER EVAL BASELINE`
- **Class:** environment/path/service/long-job control failure.
- **Evidence:** build-pmars path/provenance gaps, kv-store-grpc self-client failure, qemu/resource
  invalid rows, and unresolved EnvContract fields for install scope, lifecycle, paths, and grader
  boundary.
- **Proposed mechanism:** expand honest environment mapping; add listener/process/container
  attribution; bounded survival; provenance-aware fresh client probes; true long-job exit/log state.
- **Target eval:** environment-map and long-job/service-survival homolog smoke rows plus build-pmars,
  qemu-alpine-ssh, and compile-compcert extension rows.
- **Predicted delta:** +1 to +3 environment/service tasks and fewer invalid/path-confusion rows.
- **Sentinels:** workspace path translation, blocked network, unrelated listener, successful long build.
