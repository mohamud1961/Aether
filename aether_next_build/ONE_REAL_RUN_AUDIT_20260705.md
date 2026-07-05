# One Real Run Audit — 2026-07-05

Run: `local_goal_runs/20260705T041231Z_one_real_logsummary`

Task: `log-summary-date-ranges`

Model route: 5.4 mini for architect/solver/verifier via `run_pilot.py`.

## Result

- Reward: `0.0`
- Kernel status: `incomplete`
- Final verifier verdict: `blocked_by_tooling`
- Steps: `80`
- Classifier label: `harness_context_failure` with low confidence
- Official grader: failed on semantic counts; first mismatch was `today,ERROR`, expected `370`, got `414`.

## What Happened

- The architect config was valid and had no architect defect.
- The solver made one real attempt at step 0: it wrote `/app/summary.csv` and ran an independent recomputation check.
- The solver's method was wrong for the hidden grader semantics, but it believed its local recomputation was correct.
- The verifier repeatedly returned `uncertain_missing_evidence` because it could not see enough raw file/log evidence to independently audit the counts.
- At verifier round 7 it returned `blocked_by_tooling` with an active finding: the verifier needed readable artifact/log contents.
- After that, the solver ignored the active verifier finding and submitted the same completion claim until max steps.

## Root Causes Found

1. Structured verifier evidence requests were not being realized.
   The verifier returned `uncertain_missing_evidence` with structured requests such as `read_file` and `overlay_run_command`, but the runtime treated that as final feedback instead of executing those read-only requests.

2. Verifier inspection needed broader generic read support.
   The verifier asked for paths such as `/app/logs/2025-08-12_*.log`; `read_file` did not support globbed reads, so this kind of raw-state audit was weaker than it should be.

3. Solver ignored active verifier feedback.
   Once a blocking `blocked_by_tooling` finding existed, the kernel skipped repeat verifier calls without an intervening solver action, but the solver was still allowed to spend the remaining budget on empty `submit_outcome` turns.

4. The classifier was directionally conservative but imprecise.
   `harness_context_failure` was reasonable as a safety-leaning label because verifier evidence access failed, but the trace also proves a real model attempt happened and the output was semantically wrong.

## Fixes Applied After The Run

- `ModelHooks.verify_with_inspector` now executes structured `missing_evidence_requests` from an `uncertain_missing_evidence` verdict as read-only verifier inspections before accepting the uncertainty as final.
- The verifier protocol loop now gives one bounded JSON-protocol repair turn when the verifier emits prose instead of verdict/inspection JSON.
- `AETHER_VERIFIER_MAX_OUTPUT_TOKENS` now controls verifier output budget.
- `parse_verifier_inspection_requests` now accepts the first JSON object from mixed output, matching the verdict parser's lenient extraction.
- `run_check` inspection requests are aliased to `rerun_check`.
- `read_file` verifier inspection now supports bounded glob reads.
- Verifier-only model eval after these fixes: `verifier_only_eval_20260705_goal_mini_structured_missing_v1` produced 6/6 parse-ok, evidence-bound, actionable `needs_repair` rows.
- Full deterministic suite after fixes: `python3.11 -m pytest tests -q` → `311 passed`.

## Remaining Issue

Resolved after this audit: repeated `submit_outcome` turns when an active verifier finding requires intervening evidence now terminate as `solver_submit_stalemate` after three submit-only rounds without new evidence. This is a runtime liveness invariant, not task judgment.

No second real run was launched, per the one-run constraint.
