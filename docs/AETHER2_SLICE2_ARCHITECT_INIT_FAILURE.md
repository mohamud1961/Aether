# Aether-2 Slice 2 Architect Init Failure

Status: completed

Date: 2026-07-02

## Purpose

Slice 2 gives architect/workbench configuration failure a first-class runtime status. If the architect cannot produce a valid workbench configuration after the existing bounded repair attempt, the run is classified as agent initialization failure, not as a task attempt, solver failure, verifier failure, or benchmark result.

This preserves the ownership boundary:

- Architect owns workbench configuration.
- Harness owns schema parsing, bounded repair, and truthful run classification.
- Solver owns solving only after initialization succeeds.
- Verifier owns task-state judgement only after there is a task attempt to judge.
- Official grader evaluates only after agent termination and only for valid attempts.

## Adds

- `AgentInitializationFailure`, a typed exception for architect/workbench configuration failure before a task attempt exists.
- Result-row/eval-board representation for `agent_initialization_failure`.
- Model capability status `not_evaluated_agent_initialization_failure` for rows where no scored model run occurred.
- Harbor backend status artifact `agent_initialization_failure.json` for typed architect initialization failures.
- Contract coverage proving result rows can represent agent initialization failure separately from task failure.

## Changes

- Invalid JSON architect configuration still receives one bounded repair attempt. If repair fails, it now raises `AgentInitializationFailure` with reason code `architect_config_json_invalid_after_retry`.
- Schema-invalid architect configuration still receives one bounded repair attempt. If repair fails, it now raises `AgentInitializationFailure` with reason code `architect_config_schema_invalid_after_retry`.
- The custom eval board now treats typed architect initialization failure as:
  - `execution_status: agent_initialization_failure`
  - `model_run_attempted: false`
  - `scored_model_run_occurred: false`
- The eval substrate failure class vocabulary now includes `agent_initialization`.

## Deletes

- No files were deleted in this slice.
- The old generic `ValueError` path for unrepaired architect configuration failures is replaced for the two covered failure modes.

## Deferred

- No semantic "weak config" retry was added. The open question remains: who is allowed to judge config quality beyond schema validity?
- No broader verifier loop changes were made.
- No completion gate or deterministic task judgement changes were made.
- The current AHP profile path remains the integration surface for architect-owned workbench configuration. A future naming/carve-down slice may rename or consolidate this once runtime behavior is stable.
- Harbor backend coverage was implemented but not expanded into a dedicated Harbor test in this slice.

## Tests

Passed:

```bash
python3 -m pytest -q tests/test_aether2_run_config.py tests/test_benchmark_adapter_contracts.py tests/test_run_custom_eval_board.py::test_run_attempt_marks_agent_initialization_failure_separately
```

Result: 35 passed in 1.14s

Passed:

```bash
python3 -m pytest -q tests/test_aether2_prompts.py tests/test_aether2_run_config.py tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py tests/test_aether2_verification_feedback.py
```

Result: 47 passed in 2.30s

Passed:

```bash
python3 -m pytest -q tests/test_run_custom_eval_board.py
```

Result: 56 passed in 24.16s

Passed:

```bash
make public-tests
```

Result: 11 passed in 0.52s

Passed:

```bash
python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng
```

Result: exit 0, no output

## Risk

- The new typed exception currently lives in `harness/aether2/runtime/adaptive_profile.py`. If more initialization paths adopt the same classification, it may deserve a neutral runtime errors module.
- `agent_initialization_failure` is now represented in eval rows, but certified benchmark policy still needs to decide how scoreboards aggregate invalid initialization rows versus valid task attempts.
- The codebase had substantial preexisting dirty state. This slice avoided reverting or normalizing unrelated paths.

## Rollback

Revert the typed exception, eval board classification, Harbor backend catch path, failure-class vocabulary addition, and associated tests. That would restore generic runtime error treatment for architect configuration failure, but would also reintroduce ambiguity between initialization failure and task failure.
