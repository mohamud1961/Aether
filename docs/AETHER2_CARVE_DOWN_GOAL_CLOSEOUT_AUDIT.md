# Aether-2 Carve-Down Goal Closeout Audit

Status: local closeout complete; formal full-tree Codex review invalid due environment

Date: 2026-07-03

## Scope

Objective audited:

> Execute the Aether-2 architect-owned workbench carve-down from the approved
> build plan, starting with Slice 0 baseline evidence and proceeding
> slice-by-slice toward the target architecture while preserving the ownership
> model, recording evidence, and stopping honestly on blockers or invalid
> evidence.

This audit uses the current worktree as authority. It does not claim official
benchmark promotion. Slice 9 remains local Stage 1/sentinel evidence only.

## Requirement Audit

| Requirement | Evidence | Disposition |
| --- | --- | --- |
| Approved architecture/source-of-truth exists before build | `docs/CURRENT_ARCHITECTURE_VS_TARGET_ARCHITECTURE.md`, `docs/HARNESS_VISION.md`, `docs/AETHER2_CARVE_DOWN_BUILD_PLAN.md` | Complete |
| Slice 0 target lock and baseline evidence | `docs/AETHER2_SLICE0_BASELINE_VALIDATION.md`, `tracking/ledger/inbox/20260702T182144Z_aether2_slice0_baseline_raw.md` | Complete |
| Slice 1 prompt ownership foundation | `docs/AETHER2_SLICE1_PROMPT_OWNERSHIP_FOUNDATION.md`, `tracking/ledger/inbox/20260702T182730Z_aether2_slice1_prompt_ownership_raw.md` | Complete |
| Slice 2 architect config/init failure | `docs/AETHER2_SLICE2_ARCHITECT_INIT_FAILURE.md`, `tracking/ledger/inbox/20260702T183615Z_aether2_slice2_architect_init_failure_raw.md` | Complete |
| Slice 3 context/tool-output invariants | `docs/AETHER2_SLICE3_CONTEXT_TOOL_OUTPUT_INVARIANTS.md`, `tracking/ledger/inbox/20260702T184112Z_aether2_slice3_context_tool_output_invariants_raw.md` | Complete |
| Slice 4 bounded read-only verifier | `docs/AETHER2_SLICE4_BOUNDED_READ_ONLY_VERIFIER.md`, `tracking/ledger/inbox/20260702T184427Z_aether2_slice4_bounded_read_only_verifier_raw.md` | Complete |
| Slice 5 completion authority carve-down | `docs/AETHER2_SLICE5_COMPLETION_AUTHORITY_CARVE_DOWN.md`, `tracking/ledger/inbox/20260702T185011Z_aether2_slice5_completion_authority_carve_down_raw.md` | Complete |
| Slice 6 config surface cleanup | `docs/AETHER2_SLICE6_CONFIG_SURFACE_CLEANUP.md`, `tracking/ledger/inbox/20260702T185335Z_aether2_slice6_config_surface_cleanup_raw.md` | Complete |
| Slice 7 duplicate judgement path inventory/retirement | `docs/AETHER2_SLICE7_DUPLICATE_JUDGEMENT_PATH_INVENTORY.md`, `docs/AETHER2_SLICE7B_VERIFIER_SUPPRESSION_RETIREMENT.md`, `tracking/ledger/inbox/20260703T001345Z_aether2_slice7_duplicate_judgement_inventory_raw.md`, `tracking/ledger/inbox/20260703T002732Z_aether2_slice7b_verifier_suppression_retirement_raw.md` | Complete for Aether-2; Aether-Next deletion intentionally deferred pending production-target decision |
| Slice 8 official grader/result-row separation | `docs/AETHER2_SLICE8_GRADER_RESULT_ROW_SEPARATION.md`, `tracking/ledger/inbox/20260703T003639Z_aether2_slice8_grader_result_row_separation_raw.md` | Complete |
| Slice 9 Stage 1/sentinel evidence | `docs/AETHER2_SLICE9_STAGE1_SENTINEL_VALIDATION.md`, `tracking/local_runs/20260703T003639Z_aether2_slice9_model_smoke_nonmodel/`, `tracking/local_runs/20260703T004622Z_aether2_slice9_closeout_gpt54mini_one_rerun3/`, `tracking/ledger/inbox/20260703T004622Z_aether2_slice9_stage1_sentinel_validation_raw.md`, `tracking/ledger/inbox/20260703T011612Z_aether2_slice9_adversarial_closeout_raw.md` | Complete as local evidence; no promotion claim |
| Preserve ownership model | Slice docs plus Slice 9 adversarial fix isolating solver proof objects under `solver_proof_object` | Complete for scoped Aether-2 path |
| Record evidence/ledger updates | Raw ledger inbox files listed above | Complete |
| Review/adversarial closeout | Targeted adversarial audit found and fixed solver-proof override bug; validation passed. `codex review` CLI was attempted but invalid due sandboxed Codex state DB write failure. | Local adversarial closeout complete; full formal Codex review unavailable in this environment |

## Final Evidence Run

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

Key inspected facts:

- `fsent_02_runtime_workspace_contract` scored `pass`, `score: 1.0`,
  `model_capability.status: scored_model_attempt`.
- Top-level `verifier_acceptance` is `true` from the actual visible verifier.
- The solver proof object is preserved as `solver_self_report` and still
  claims `claimed_verifier_acceptance: false`, proving it no longer owns row
  authority.
- `trusted_promotion_evidence` remains `false`.
- `run_result.json` still records `verifier_clean: false` and
  `finalize_reason: implicit_stop`; this is a recorded follow-up question, not
  promotion evidence.

## Validation

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

## Review Gate

Targeted manual/adversarial review:

- Inspected Slice 9 result-row ownership against final evidence.
- Accepted finding: solver proof object could override row authority.
- Fix: solver proof object fields are now isolated under
  `solver_proof_object` as self-report.
- Regression: `test_solver_proof_object_cannot_override_verifier_or_grader_authority`.

Codex review CLI attempt:

```bash
{ printf '%s\n' 'Review this scoped Slice 9 patch for correctness bugs, ownership-boundary regressions, and missing tests. Focus only on the diff below; ignore unrelated repository state. Report only actionable findings.'; git diff -- tools/run_custom_eval_board.py tests/test_run_custom_eval_board.py harness/aether2/runtime/bridge_harbor.py tests/test_aether2_harbor_executor.py; } | codex review -c service_tier='"flex"' -
```

Result: invalid due environment. The CLI attempted to initialize Codex app
state under `/Users/mohamud/.codex/state_5.sqlite` and failed with
`attempt to write a readonly database` / `Operation not permitted`. A whole-tree
`codex review --uncommitted` was also not suitable because the checkout
contains a large unrelated dirty reset tree.

## Residual Risks

- No official promotion claim: Slice 9 is local evidence only.
- Aether-Next duplicate judgement paths were not deleted because the production
  target decision remained explicitly unresolved in Slice 7.
- Internal Aether-2 `verifier_clean` can diverge from external visible verifier
  and official grader pass on the local sentinel. This is recorded as the next
  policy/evidence question before promotion.

## Closeout Decision

The approved Aether-2 carve-down slices are executed through Slice 9 for the
scoped Aether-2 path, with evidence and raw ledger updates. The result is ready
for the next decision: whether to require internal verifier alignment before a
broader certified Linux/container sentinel board and any promotion claim.
