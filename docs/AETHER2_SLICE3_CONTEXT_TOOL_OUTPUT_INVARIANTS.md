# Aether-2 Slice 3 Context And Tool-Output Invariants

Status: completed

Date: 2026-07-02

## Purpose

Slice 3 makes recent tool outputs, verifier feedback, artifact observations, failure summaries, and receipt continuity an invariant context floor. The architect may shape context priorities, but cannot silently remove the recent evidence needed by the solver or verifier to avoid repeated actions and false completion.

This preserves the ownership boundary:

- Architect owns context policy above the invariant floor.
- Harness owns context mechanics, receipt continuity, redaction, and bounded evidence summaries.
- Solver and verifier consume recent evidence instead of relying on harness-side stuckness compensation.

## Adds

- `INVARIANT_CONTEXT_PACK_SECTIONS` in `harness/aether2/runtime/run_config.py`.
- Tests proving architect-provided context policy cannot exclude recent evidence sections or zero out their budgets.
- Tests proving compact receipt continuity preserves recent `run_command`, `read_file`, `write_file`, tool-error, artifact-observation, verifier-feedback, and evidence-reference facts even when the architect tries to exclude those sections.
- Model-visible evidence refs now include event IDs, event summaries, step, event type, and `raw_log_available: true` rather than host raw-log paths.

## Changes

- `validate_context_pack_policy` now always restores invariant context sections:
  - `current_plan`
  - `recent_steps`
  - `recent_failures`
  - `verifier_feedback`
  - `artifact_observations`
  - `evidence_refs`
- Architect-requested `exclude_sections` no longer removes invariant recent-evidence sections.
- Context budgets now have small evidence-preserving floors:
  - `receipt_event_budget >= 6`
  - `failure_event_budget >= 1`
  - `tool_result_budget >= 2`
  - `verifier_feedback_budget >= 1`
  - `artifact_observation_budget >= 1`
- Receipt evidence refs no longer expose `raw_log_path` to model-visible context. They preserve durable receipt references without leaking host paths.

## Deletes

- No files were deleted in this slice.
- The ability for architect context policy to silently remove recent evidence sections was removed.

## Deferred

- No broader retrieval or replay engine work.
- No verifier-loop changes.
- No no-progress/repeat-guidance deletion yet. That should wait until enough repeated-action tests prove the invariant context floor replaces that compensation safely.
- No full model-backed repeated-action row was run in this slice.

## Tests

Passed:

```bash
python3 -m pytest -q tests/test_aether2_run_config.py tests/test_compaction_receipt_continuity.py tests/test_aether2_compactor.py tests/test_aether2_transcript_repair.py
```

Result: 43 passed in 0.69s

Passed:

```bash
python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng
```

Result: exit 0, no output

Passed:

```bash
python3 -m pytest -q tests/test_aether2_prompts.py tests/test_aether2_run_config.py tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py tests/test_aether2_verification_feedback.py tests/test_compaction_receipt_continuity.py tests/test_aether2_compactor.py tests/test_aether2_transcript_repair.py
```

Result: 68 passed in 3.83s

Passed:

```bash
python3 -m pytest -q tests/test_run_custom_eval_board.py
```

Result: 56 passed in 30.64s

Passed:

```bash
make public-tests
```

Result: 11 passed in 1.08s

## Risk

- The invariant floor increases minimum context payload size. The preserved content is compact receipt data, not full raw logs.
- The six-event recent receipt floor is a policy choice. It is intentionally small but may need tuning after model-backed repeated-action evals.
- Raw log paths are hidden from model-visible context. This preserves redaction boundaries, but consumers must use receipt IDs/artifacts rather than relying on host paths in model context.

## Rollback

Revert `INVARIANT_CONTEXT_PACK_SECTIONS`, the policy-floor changes in `validate_context_pack_policy`, the receipt evidence-ref shape change, and the associated tests. That would restore the prior behavior where architect context policy could remove recent tool/verifier evidence and where evidence refs attempted to include raw host paths before model-visible sanitization.
