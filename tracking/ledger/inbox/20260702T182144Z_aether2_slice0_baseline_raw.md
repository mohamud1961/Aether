RAW_LEDGER_UPDATE
- actor: Codex GPT-5
- task: Activate long-running Aether-2 carve-down goal and execute Slice 0 baseline evidence
- event_type: decision
- summary: Created the active long-running goal for the Aether-2 architect-owned workbench carve-down, applied the attached review edits to docs/AETHER2_CARVE_DOWN_BUILD_PLAN.md, and completed Slice 0 baseline validation with no runtime code changes.
- observations: The plan now states it is the long-running goal baseline, Slice 0 is ready for execution, and runtime coding remains blocked until Slice 1 or another code slice is explicitly approved. It adds a top-level acceptance rule that a slice counts as progress only if it moves task-specific intelligence out of the harness and into the architect, solver, or verifier unless the change is a generic runtime invariant. Slice 1 now explicitly requires tests proving no static behavioural solver prompt competes with the architect-authored solver prompt when supplied and proving remaining harness prompt content is mechanical/tool/action-schema/safety/runtime-invariant only. Baseline validation passed: `python3 -m pytest -q tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py` -> 6 passed; `python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng` -> exit 0 no output; `make public-tests` -> 11 passed.
- inference: Slice 0 is complete and provides a clean baseline for the first code slice. The recommended next implementation boundary is Slice 1 Prompt Ownership Foundation, limited to prompt ownership, "official grader evaluates" wording, stable prefix behavior, and focused tests; it should not touch verifier/completion semantics or add task-specific checks.
- evidence_paths: docs/AETHER2_CARVE_DOWN_BUILD_PLAN.md; docs/AETHER2_SLICE0_BASELINE_VALIDATION.md; docs/CURRENT_ARCHITECTURE_VS_TARGET_ARCHITECTURE.md; tracking/ledger/inbox/20260702T181426Z_aether2_carve_down_build_plan_raw.md
- affected_components: Aether-2 planning governance; prompt ownership acceptance criteria; Slice 0 baseline evidence; long-running goal execution state
- decision_change: Build plan execution has started under a long-running goal. Slice 0 is complete. Runtime code changes remain deferred until Slice 1 or another code slice is approved.
- unresolved_questions: Whether to start Slice 1 immediately under the user's "set goal execute" instruction or wait for explicit Slice 1 approval; exact implementation path for architect prompt slots inside harness/aether2 remains to be mapped at Slice 1 start.
- confidence: high
- commit_message: docs: record Aether-2 Slice 0 baseline validation

Note: tracking/ledger/tools/record_update.py is not present in this checkout, so this raw update was persisted directly under tracking/ledger/inbox using the repository's existing raw handoff file pattern.
