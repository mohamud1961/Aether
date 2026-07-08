# Aether-2 Slice 7B Verifier Suppression Retirement

Status: completed

Date: 2026-07-03

## Purpose

Slice 7B removes the remaining Aether-2 path where active verifier blockers
could prevent a fresh verifier call. That path was useful as a throttle, but it
also let the harness synthesize a verifier-shaped rejection from deterministic
blocker-relevance logic. Under the ownership model, blocker records are
evidence; the verifier owns task-state judgement.

This slice is scoped to `harness/aether2/` and is safe under the unresolved
production-target question. It does not delete or relabel Aether-Next code.

## Adds

- Regression coverage proving active blockers are verifier-visible evidence, not
  verifier suppression.

## Changes

- `_run_verification_rounds` always calls the verifier for verification rounds,
  including periodic/final feedback with active blockers.
- Blocker relevance remains only as ledger lifecycle bookkeeping for
  `mark_blockers_candidate_resolved`.
- Result payloads no longer report retired zero-only telemetry fields.

## Deletes

- Removed the active `should_suppress_verifier_call(...)` branch from
  `harness/aether2/control/verification_rounds.py`.
- Deleted `_build_suppressed_blocker_report(...)` and `_active_blockers(...)`
  from `harness/aether2/control/completion.py`.
- Removed exported `should_suppress_verifier_call` from
  `harness/aether2/traces/blockers.py`, `harness/aether2/traces/delta.py`,
  `harness/aether2/traces/__init__.py`, and `harness/aether2/__init__.py`.
- Removed `suppressed_verifier_calls` and `completion_precheck_rejections` from
  `RunResult`, loop state, Harbor result summaries, and
  `tools/run_tbench_model_backed.py`.

## Deferred

- Aether-Next duplicate judgement paths remain untouched until the production
  harness decision is explicit.
- `_build_completion_evidence_gate_report(...)` remains because it now produces
  verifier-visible evidence-floor context rather than a harness veto.
- Proof-state and repeat-guidance surfaces remain pending eval-backed cleanup.
- Stage 1/sentinel validation is still required before promotion.

## Tests

Passed:

```bash
python3 -m pytest -q tests/test_aether2_verification_feedback.py tests/test_aether2_hooks.py tests/test_aether2_launch_integrity.py
```

Result: 32 passed in 32.41s

Passed:

```bash
python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng
```

Result: exit 0, no output

Passed:

```bash
python3 -m pytest -q tests/test_aether2_prompts.py tests/test_aether2_run_config.py tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py tests/test_aether2_verification_feedback.py tests/test_compaction_receipt_continuity.py tests/test_aether2_compactor.py tests/test_aether2_transcript_repair.py tests/test_aether2_hooks.py tests/test_aether2_post_upgrade_behaviors.py
```

Result: 96 passed in 70.60s

Passed:

```bash
make public-tests
```

Result: 11 passed in 1.06s

Passed:

```bash
python3 -m pytest -q tests/test_run_custom_eval_board.py tests/test_benchmark_adapter_contracts.py tests/test_benchmark_adapter_readiness.py
```

Result: 77 passed in 34.38s

Passed:

```bash
python3 -m pytest -q tests/test_harbor_agent_adapter.py tests/test_aether2_harbor_executor.py tests/test_aether2_harbor_backend_read.py
```

Result: 23 passed in 3.83s

## Risk

- Removing verifier suppression can increase verifier calls on periodic/final
  feedback rounds, which may cost more tokens. The tradeoff is intentional:
  cost throttling must not own semantic readiness.
- Removing result fields can affect consumers that read
  `suppressed_verifier_calls` or `completion_precheck_rejections`. Those fields
  no longer had a real producer after the suppression path was deleted.

## Rollback

Restore the suppression branch, suppressed-blocker report helper, public export,
result fields, and old tests. That would also restore a shared-ownership bug
where deterministic blocker relevance could stand in for verifier judgement.
