# Aether-2 Slice 8 Grader Result-Row Separation

Status: completed

Date: 2026-07-03

## Purpose

Slice 8 makes the official grader boundary explicit in machine-readable
artifacts and custom eval result rows. The official grader evaluates only after
the agent attempt; it is not verifier feedback, not solver-visible context, and
not evidence that an invalid agent attempt should be counted as a scored model
capability run.

This slice does not add new judgement logic. It clarifies ownership:

- verifier validity says whether the visible verifier/readiness check was valid;
- grader validity records official post-agent measurement artifacts;
- task truth is pass/fail only for completed attempts;
- invalid initialization, verifier, launch, and environment attempts remain
  invalid rather than becoming task failures or capability scores.

## Adds

- A regression proving an invalid visible-verifier attempt with a completed
  model run and a passing official grader artifact is not counted as a scored
  model capability run.
- A Harbor regression proving `grader_reward` is attached from the reward file
  after the run result exists, and completed manifests label the attribution as
  post-agent, non-agent-visible, external measurement.
- Result-row `task_truth_status` and `scoreable_attempt` fields for clearer
  invalid/pass/fail separation.
- Scoreboard `model_capability.status_counts` for separating scored attempts
  from invalid or unscored model executions.

## Changes

- Custom eval result rows now compute `scored_model_run_occurred` only when the
  attempt completed, the model run completed, the grader ran, and the attempt
  was not an infrastructure/no-action timeout.
- Invalid attempts with official grader artifacts keep those artifacts under
  `grader_validity`, but `score` is `None` and model capability status is
  `not_evaluated_invalid_attempt`.
- `grader_validity` now records `authority:
  official_post_agent_measurement` and `agent_visible: false`.
- Harbor completed manifests now record:
  - `official_grader_phase: post_agent`;
  - `official_grader_agent_visible: false`;
  - `official_grader_authority: external_measurement`.

## Deletes

- No runtime mechanism was deleted.
- The row semantics delete the prior ambiguity where a grader artifact could
  make an invalid model attempt look like a scored capability attempt.

## Deferred

- Certified benchmark-native promotion remains deferred until Stage 1 evidence
  and sentinel validation.
- Broader result-row schema consolidation remains outside this slice unless a
  downstream consumer requires migration.

## Tests

Passed:

```bash
python3 -m pytest -q tests/test_aether2_harbor_executor.py::test_harbor_grader_reward_is_post_agent_result_attribution tests/test_run_custom_eval_board.py::test_invalid_verifier_model_attempt_is_not_scored_by_grader_result tests/test_run_custom_eval_board.py::test_run_attempt_records_verifier_and_grader_separately tests/test_run_custom_eval_board.py::test_build_attempt_scoreboard_does_not_score_runtime_error_attempts tests/test_run_custom_eval_board.py::test_run_attempt_marks_agent_initialization_failure_separately
```

Result: 5 passed in 1.39s

Passed:

```bash
python3 -m py_compile harness/aether2/runtime/bridge_harbor.py tests/test_aether2_harbor_executor.py tools/run_custom_eval_board.py tests/test_run_custom_eval_board.py
```

Result: exit 0, no output

Passed:

```bash
python3 -m pytest -q tests/test_run_custom_eval_board.py tests/test_benchmark_adapter_contracts.py tests/test_benchmark_adapter_readiness.py
```

Result: 78 passed in 39.99s

Passed:

```bash
python3 -m pytest -q tests/test_harbor_agent_adapter.py tests/test_aether2_harbor_executor.py tests/test_aether2_harbor_backend_read.py
```

Result: 24 passed in 4.38s

Passed:

```bash
python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng
```

Result: exit 0, no output

Passed:

```bash
make public-tests
```

Result: 11 passed in 1.06s

Passed:

```bash
python3 -m pytest -q tests/test_aether2_prompts.py tests/test_aether2_run_config.py tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py tests/test_aether2_verification_feedback.py tests/test_compaction_receipt_continuity.py tests/test_aether2_compactor.py tests/test_aether2_transcript_repair.py tests/test_aether2_hooks.py tests/test_aether2_post_upgrade_behaviors.py
```

Result: 96 passed in 65.43s

## Risk

- Strict separation can reduce the number of attempts counted as scored model
  runs when verifier, launch, or environment validity fails. That is intended:
  invalid substrate should not masquerade as model task failure or success.
- Consumers that previously treated `score` as always present for model-backed
  rows need to read `task_truth_status`, `grader_validity`, and
  `model_capability.status` together.

## Rollback

Revert the result-row and manifest attribution changes. That would restore an
ambiguous boundary where post-agent grader artifacts could be confused with
agent-visible verifier evidence or scored model capability runs.
