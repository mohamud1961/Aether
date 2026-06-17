# Raw Ledger Update

- recorded_at_utc: 2026-06-11T17:34:34.649704+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex-orchestrator
- task: aether2_vm_lifecycle_scripts_gap_closure
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 9a9ce553e0fa3b1abed0a529cd19a2426958fcd2936f80ff38815c5d7b0d0ade
- commit_message: HOLD - add missing VM lifecycle scripts and smoke tests
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-11/173434_codex-orchestrator_aether2-vm-lifecycle-scripts-gap-closure_9a9ce553e0.md

```text
RAW_LEDGER_UPDATE
- actor: codex-orchestrator
- task: aether2_vm_lifecycle_scripts_gap_closure
- event_type: implementation
- summary: Added the two missing Aether-2 VM lifecycle scripts and a focused smoke test after verifying they were absent from the live checkout despite earlier status assumptions.
- observations: `scripts/deallocate_harnesseng_vm.sh` and `scripts/configure_harnesseng_vm_autoshutdown.sh` did not exist in `scripts/` when the live tree was re-checked. Both scripts were created in the repo root `scripts/` directory, marked executable, and validated with `bash ... --dry-run --help`. The smoke test `tests/test_aether2_vm_lifecycle_scripts.py` passed.
- inference: The earlier ledger/status assumption that the VM lifecycle scripts were already present was false-complete; the orchestration record now reflects the scripts as created and smoke-checked.
- evidence_paths: /Users/mohamud/Downloads/harnesseng/scripts/deallocate_harnesseng_vm.sh; /Users/mohamud/Downloads/harnesseng/scripts/configure_harnesseng_vm_autoshutdown.sh; /Users/mohamud/Downloads/harnesseng/tests/test_aether2_vm_lifecycle_scripts.py; pytest output `2 passed in 0.10s`.
- affected_components: scripts/deallocate_harnesseng_vm.sh; scripts/configure_harnesseng_vm_autoshutdown.sh; tests/test_aether2_vm_lifecycle_scripts.py; tracking/collab/aether2_build_orchestration/orchestration_ledger.md; tracking/collab/aether2_build_orchestration/decision_log.md
- decision_change: VM lifecycle scripts are now treated as required in-tree surfaces that must be smoke-checked; prior claims of presence are corrected to absent-before-fix.
- unresolved_questions: The exact Azure CLI auto-shutdown policy parameters may need later refinement if the operational team wants a stricter policy than the current `--time`-based wrapper.
- confidence: high
- commit_message: HOLD - add missing VM lifecycle scripts and smoke tests
```
