# Aether-2 Slice 5 Completion Authority Carve-Down

Status: completed

Date: 2026-07-02

## Purpose

Slice 5 demotes the no-evidence `task_done` completion gate from harness-side verifier-shaped rejection to verifier-visible evidence. The verifier now sees the generic evidence-floor warning and decides readiness. The harness still records the concern, but it no longer substitutes its own semantic verdict for the verifier.

This preserves the ownership boundary:

- Verifier owns task-state judgement.
- Harness owns generic runtime/evidence-floor instrumentation.
- Solver owns repair after verifier feedback.
- Official grader remains post-agent measurement only.

## Adds

- `completion_runtime_floor` evidence in the verifier `action_digest` when `task_done` has no replayed checks or independent runtime/service/session evidence.
- A regression test proving a no-evidence `task_done` calls the verifier with `completion_runtime_floor` instead of incrementing `completion_precheck_rejections`.
- Updated loop-order test proving premature `task_done` now runs `normal -> verifier -> normal` rather than `normal -> normal -> verifier`.

## Changes

- `_run_verification_rounds` now converts `_build_completion_evidence_gate_report(...)` into verifier-visible `action_digest["completion_runtime_floor"]`.
- The completion evidence floor no longer creates the active discrepancy report before the verifier runs.
- Active-blocker verifier suppression is no longer applied to `task_done`; completion claims get a verifier pass.

## Deletes

- No files were deleted in this slice.
- The no-evidence `task_done` harness-side precheck veto path was removed from the active verifier-round path.

## Deferred

- Full deletion or renaming of `_build_completion_evidence_gate_report`; it still builds the generic floor evidence payload.
- Further cleanup of `completion_precheck_rejections`, whose name mainly applied to suppressed non-`task_done` verifier calls, was completed in Slice 7B.
- Broader proof-state and repeat-guidance deletion. Those need eval evidence showing the verifier/context path covers the same failure pressure.
- Model-backed completion authority rows were not run in this slice.

## Tests

Passed:

```bash
python3 -m pytest -q tests/test_aether2_verification_feedback.py tests/test_aether2_hooks.py tests/test_aether2_post_upgrade_behaviors.py
```

Result: 37 passed in 61.04s

Passed:

```bash
python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng
```

Result: exit 0, no output

Passed:

```bash
python3 -m pytest -q tests/test_aether2_prompts.py tests/test_aether2_run_config.py tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py tests/test_aether2_verification_feedback.py tests/test_compaction_receipt_continuity.py tests/test_aether2_compactor.py tests/test_aether2_transcript_repair.py tests/test_aether2_hooks.py tests/test_aether2_post_upgrade_behaviors.py
```

Result: 94 passed in 81.87s

Passed:

```bash
python3 -m pytest -q tests/test_run_custom_eval_board.py
```

Result: 56 passed in 36.37s

Passed:

```bash
make public-tests
```

Result: 11 passed in 1.10s

## Risk

- Slice 7B removed the old `completion_precheck_rejections` and `suppressed_verifier_calls` telemetry fields after deleting the suppression path.
- The generic evidence floor is still represented by a function named `_build_completion_evidence_gate_report`; that name can imply authority it no longer has in the `task_done` path.
- Suppressed non-`task_done` verifier calls were removed in Slice 7B; active blockers now remain verifier-visible evidence instead of suppressing verifier judgement.

## Rollback

Revert the `completion_runtime_floor` action-digest change and the updated tests. That would restore the prior behavior where a no-evidence `task_done` could be rejected by harness-side precheck logic before the verifier judged task readiness.
