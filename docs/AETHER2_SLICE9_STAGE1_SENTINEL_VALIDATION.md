# Aether-2 Slice 9 Stage 1 Sentinel Validation

Status: completed as local Stage 1/sentinel evidence; no promotion claim

Date: 2026-07-03

## Purpose

Slice 9 validates the carved-down Aether-2 path with bounded evidence before
promotion or broader variant work. This slice is intentionally evidence-first:
run targeted rows, inspect artifacts, classify issues, and record
keep/kill/iterate without adding new mechanisms unless evidence exposes a
substrate or row-semantics bug.

## Adds

- Local run evidence under:
  - `tracking/local_runs/20260703T003639Z_aether2_slice9_model_smoke_nonmodel/`
  - `tracking/local_runs/20260703T004622Z_aether2_slice9_closeout_gpt54mini_one_rerun3/`
- A regression proving a valid model attempt with a passing visible verifier
  and passing official grader is represented as a scored model attempt.
- A regression proving a solver-written proof object cannot override verifier
  acceptance, official task truth, score, or top-level evidence artifact
  references.
- A Slice 9 documentation bundle with artifact paths, outcome, risks, and
  keep/kill/iterate decision.

## Changes

- `tools/run_custom_eval_board.py` now uses `attempt_completed` as the success
  execution status for completed attempts. The first model-backed Slice 9 run
  exposed that the old `completed` status caused a real pass to remain
  `executed_model_attempt_unscored`.
- `tests/test_run_custom_eval_board.py` now covers both sides of the Slice 8/9
  row boundary:
  - invalid visible-verifier attempts with grader artifacts are not scored;
  - valid model attempts with passing grader artifacts are scored.
- Solver proof objects are now represented as `solver_proof_object` with
  `authority: solver_self_report`. The row keeps claimed proof fields for audit
  but derives `verifier_acceptance`, `evidence_summary`, task truth, score, and
  top-level `unresolved_risks` from harness/verifier/grader execution.

## Deletes

- No mechanisms were deleted.
- No judgement authority was added to the harness.

## Evidence

### Non-Model Substrate Smoke

Command:

```bash
python3 tools/run_custom_eval_board.py --board eval_suite/whole_harness/final_harness_v1/local_custom_eval_model_smoke_v1.yaml --output-root tracking/local_runs/20260703T003639Z_aether2_slice9_model_smoke_nonmodel --run-attempts --list
```

Result:

```text
fsent_02_runtime_workspace_contract    attempt_completed    failed    failed
fsent_04_retrieval_reduction_closure   attempt_completed    failed    failed
{"mode": "run_attempts", "harness": "aether2", "row_count": 2, "no_model_run_performed": true}
```

Artifacts:

- `tracking/local_runs/20260703T003639Z_aether2_slice9_model_smoke_nonmodel/scoreboard.json`
- `tracking/local_runs/20260703T003639Z_aether2_slice9_model_smoke_nonmodel/attempt_rows.jsonl`

Interpretation:

- Fixture, visible-verifier, grader, cleanup, and row-writing substrate ran for
  two sentinel rows.
- Both rows failed because no solver/model produced final submissions. This is
  expected substrate evidence, not model capability evidence.

### Model-Backed Sentinel

Command:

```bash
python3 tools/run_custom_eval_board.py --board eval_suite/whole_harness/final_harness_v1/local_custom_eval_model_smoke_v1.yaml --output-root tracking/local_runs/20260703T004622Z_aether2_slice9_closeout_gpt54mini_one_rerun3 --run-attempts --list --model-route azure_gpt54_mini_env --max-model-rows 1
```

Result:

```text
fsent_02_runtime_workspace_contract    attempt_completed    passed    passed
fsent_04_retrieval_reduction_closure   attempt_completed    failed    failed
{"mode": "run_attempts", "harness": "aether2", "row_count": 2, "no_model_run_performed": false}
```

Scoreboard summary:

```json
{
  "execution_status_counts": {"attempt_completed": 2},
  "grader_status_counts": {"failed": 1, "passed": 1},
  "model_capability": {
    "not_evaluated_no_model_attempt": 1,
    "scored_model_run_count": 1,
    "status_counts": {
      "not_evaluated_no_model_attempt": 1,
      "scored_model_attempt": 1
    }
  },
  "verifier_status_counts": {"failed": 1, "passed": 1}
}
```

Scored row:

- Row: `fsent_02_runtime_workspace_contract`
- Route: `openai_api:gpt-5.4-mini`
- Model calls: 13
- Steps: 8
- Task truth: `pass`
- Score: 1.0
- Model capability status: `scored_model_attempt`
- Visible verifier: passed
- Official grader: passed
- Top-level verifier acceptance: true
- Solver proof object: present as `solver_self_report`; it claimed
  `verifier_acceptance: false`, but that did not override the verifier result.

Key artifacts:

- `tracking/local_runs/20260703T004622Z_aether2_slice9_closeout_gpt54mini_one_rerun3/scoreboard.json`
- `tracking/local_runs/20260703T004622Z_aether2_slice9_closeout_gpt54mini_one_rerun3/attempt_rows.jsonl`
- `tracking/local_runs/20260703T004622Z_aether2_slice9_closeout_gpt54mini_one_rerun3/attempts/fsent_02_runtime_workspace_contract/artifacts/grader_output.json`
- `tracking/local_runs/20260703T004622Z_aether2_slice9_closeout_gpt54mini_one_rerun3/attempts/fsent_02_runtime_workspace_contract/artifacts/visible_verifier_output.txt`
- `tracking/local_runs/20260703T004622Z_aether2_slice9_closeout_gpt54mini_one_rerun3/attempts/fsent_02_runtime_workspace_contract/pack/solver_pack/workspace/runtime/out/final_submission.json`
- `tracking/local_runs/20260703T004622Z_aether2_slice9_closeout_gpt54mini_one_rerun3/attempts/fsent_02_runtime_workspace_contract/pack/solver_pack/workspace/runtime/out/aether2_proof_object.json`
- `tracking/local_runs/20260703T004622Z_aether2_slice9_closeout_gpt54mini_one_rerun3/attempts/fsent_02_runtime_workspace_contract/artifacts/model_run/run_result.json`

Artifact truth inspected:

- `grader_output.json` records deterministic `verdict: pass`, `score: 1.0`,
  `failure_class: none`, and no reason codes.
- `visible_verifier_output.txt` records return code 0 and stdout
  `{"passed": true}`.
- `final_submission.json` contains the required contract fields:
  `python_command`, `workspace_root`, `runner_command`, and
  `runtime_classification`.
- `attempt_rows.jsonl` records top-level `verifier_acceptance: true`,
  `unresolved_risks: []`, and `solver_proof_object.claimed_verifier_acceptance:
  false`.
- `run_result.json` records `model_calls: 13`, `steps: 8`,
  `finalize_reason: implicit_stop`, and `verifier_clean: false`.

## Classification

Outcome: iterate.

The model-backed sentinel produced a real scoreable pass on one local
TerminalBench-style sentinel and preserved the official grader boundary.
However, this is not promotion evidence:

- it is a local run, not a certified benchmark-native Linux/container run;
- the board has only one model-backed row plus one non-model control row;
- the Aether-2 internal verifier did not mark the run clean even though the
  external visible verifier and official grader passed;
- the solver proof object can contain stale or conservative self-reported
  verifier claims, now explicitly isolated from row authority.

The next concrete action is to run a slightly broader model-backed sentinel
board after deciding whether internal verifier acceptance must align with
official pass before promotion eligibility.

## Tests

Passed:

```bash
python3 -m pytest -q tests/test_run_custom_eval_board.py::test_solver_proof_object_cannot_override_verifier_or_grader_authority tests/test_run_custom_eval_board.py::test_run_attempt_marks_agent_initialization_failure_separately tests/test_run_custom_eval_board.py::test_valid_model_attempt_with_passing_grader_is_scored
```

Result: 3 passed in 1.17s

Passed:

```bash
python3 -m py_compile tools/run_custom_eval_board.py tests/test_run_custom_eval_board.py
```

Result: exit 0, no output

Passed:

```bash
python3 -m pytest -q tests/test_run_custom_eval_board.py tests/test_benchmark_adapter_contracts.py tests/test_benchmark_adapter_readiness.py
```

Result: 80 passed in 53.26s

Passed:

```bash
python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng
```

Result: exit 0, no output

Passed:

```bash
make public-tests
```

Result: 11 passed in 1.14s

Passed:

```bash
python3 -m pytest -q tests/test_harbor_agent_adapter.py tests/test_aether2_harbor_executor.py tests/test_aether2_harbor_backend_read.py
```

Result: 24 passed in 6.42s

Passed:

```bash
python3 -m py_compile tools/run_custom_eval_board.py tests/test_run_custom_eval_board.py harness/aether2/runtime/bridge_harbor.py tests/test_aether2_harbor_executor.py
```

Result: exit 0, no output

Passed:

```bash
python3 -m pytest -q tests/test_aether2_prompts.py tests/test_aether2_run_config.py tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py tests/test_aether2_verification_feedback.py tests/test_compaction_receipt_continuity.py tests/test_aether2_compactor.py tests/test_aether2_transcript_repair.py tests/test_aether2_hooks.py tests/test_aether2_post_upgrade_behaviors.py
```

Result: 96 passed in 75.79s

## Risk

- A local scored pass can be overread as promotion evidence. It is not.
- Internal verifier cleanliness and official grader pass are currently able to
  diverge on this row. That may be acceptable for post-agent measurement, but
  it must be decided before promotion policy relies on these rows.
- Solver proof objects can preserve stale verifier-feedback claims after the
  external visible verifier passes. They are now retained as solver self-report,
  not as top-level row authority.

## Rollback

Do not roll back from this evidence. The code fixes are the status vocabulary
correction from `completed` to `attempt_completed` and the proof-object
ownership separation. Revert only if a consumer requires a different canonical
row schema and the scorer is migrated with it.
