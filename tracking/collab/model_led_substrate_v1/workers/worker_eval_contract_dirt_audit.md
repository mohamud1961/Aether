# Worker D Eval Contract Dirt Audit

## Summary

I audited the prioritized custom eval rows separately from the harness architecture and patched the rows whose visible contract could be brought into alignment without leaking hidden answers or weakening the intended pressure.

## Row-By-Row Classification

- `fhard_03_filesystem_decoy_patch`: `eval_contract_dirty`, quarantine / diagnostic only.
- `fhard_05_structured_retrieval_reduction`: `environment_dirty`, quarantine / diagnostic only.
- `fhard_06_original_repo_recovery_flagship`: `contamination_dirty`, rerun only as a contamination-sensitive sentinel.
- `fhard_07_original_tool_schema_workspace_mix`: `eval_contract_dirty`, ready for rerun.
- `fsent_01_tool_call_bfcl_composite`: `eval_contract_dirty`, quarantine / diagnostic only.
- `fsent_05_long_handoff_composition_smoke`: `eval_contract_dirty`, ready for rerun.

## Why These Calls

- `fhard_03_filesystem_decoy_patch` is not safely fixable from the current pack state because the solver workspace lacks the actual `apps/ledger/src/` source tree, so the visible contract can be satisfied syntactically without any real patch target.
- `fhard_05_structured_retrieval_reduction` is not safely fixable in this environment because the workspace has no clip, outbound fetch was unavailable, and the media/OCR tools were absent.
- `fhard_06_original_repo_recovery_flagship` now has a stronger visible verifier, but the latest run still shows a hidden-truth access attempt, so the remaining issue is solver contamination discipline rather than a pure contract gap.
- `fhard_07_original_tool_schema_workspace_mix` was under-checking the dispatch contract; the visible verifier now derives the expected ticket/workspace directly from the visible live snapshot and checks the final submission fields too.
- `fsent_01_tool_call_bfcl_composite` is still hidden-answer anchored. The expected owner/ticket pair is not inferable from the visible workspace, so I left it quarantined instead of leaking the hidden answer into the visible contract.
- `fsent_05_long_handoff_composition_smoke` had a weak visible check that only validated presence. The visible check now verifies bundle identity, bundle hash, and minimum handoff depth.

## Changed Files

- `tracking/collab/final_harness_eval_suite/task_packs/hard/fhard_07_original_tool_schema_workspace_mix/solver_pack/workspace/project/scripts/visible_verify.py`
- `tracking/collab/final_harness_eval_suite/task_packs/composition/fsent_05_long_handoff_composition_smoke/solver_pack/workspace/handoff/checks/visible_check.py`
- `tracking/collab/final_harness_eval_suite/task_packs/hard/fhard_06_original_repo_recovery_flagship/solver_pack/workspace/repo/scripts/verify_recovery.py`
- `tests/test_final_harness_eval_suite_visible_contracts.py`

## Tests Run

- `python3 -m py_compile tracking/collab/final_harness_eval_suite/task_packs/hard/fhard_07_original_tool_schema_workspace_mix/solver_pack/workspace/project/scripts/visible_verify.py tracking/collab/final_harness_eval_suite/task_packs/composition/fsent_05_long_handoff_composition_smoke/solver_pack/workspace/handoff/checks/visible_check.py tracking/collab/final_harness_eval_suite/task_packs/hard/fhard_06_original_repo_recovery_flagship/solver_pack/workspace/repo/scripts/verify_recovery.py`
- `pytest -q tests/test_final_harness_eval_suite_visible_contracts.py`

## Quarantine List

- `fhard_03_filesystem_decoy_patch`
- `fhard_05_structured_retrieval_reduction`
- `fsent_01_tool_call_bfcl_composite`

## Ready For Rerun

- `fhard_07_original_tool_schema_workspace_mix`
- `fsent_05_long_handoff_composition_smoke`
- `fhard_06_original_repo_recovery_flagship` as a contamination-sensitive rerun, not a promotion candidate

## Notes For The Next Pass

- No runner/core changes were made.
- The new regression file covers the patched visible contracts with no-model smoke checks.
- The remaining quarantine rows need new fixture/workspace evidence before they can be made fair enough to rerun.
