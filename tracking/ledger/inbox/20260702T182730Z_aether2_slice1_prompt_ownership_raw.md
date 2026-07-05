RAW_LEDGER_UPDATE
- actor: Codex GPT-5
- task: Execute Slice 1 Prompt Ownership Foundation for the Aether-2 architect-owned workbench carve-down
- event_type: implementation
- summary: Implemented the Slice 1 prompt ownership foundation. Added a distinct harness-owned MECHANICAL_SYSTEM_PROMPT, kept legacy SYSTEM_PROMPT as baseline compatibility, elevated architect/AHP solver prompts into the system prompt over the mechanical frame for AHP startup, added verifier prompt config/plumbing, and changed prompt wording from "grader decides" to "official grader evaluates after the agent terminates."
- observations: AHP startup now passes MECHANICAL_SYSTEM_PROMPT into the adaptation path and always composes the generated solver prompt into [architect_solver_prompt]. The static compatibility SYSTEM_PROMPT no longer competes with generated solver prompts in the AHP path. HarnessRunConfig now exposes verifier_system_prompt through VerifierPolicy.system_prompt, and verification rounds pass it into verify_fresh_context, where it is placed above the harness-owned verifier JSON/schema contract as [architect_verifier_prompt]. Focused tests assert no static behavioral solver prompt remains when an architect prompt is supplied, and that the remaining mechanical frame is limited to tool/action schema, safety, grader separation, and runtime invariants.
- inference: Slice 1 moved task-specific prompt intelligence out of the static harness prompt and into architect-owned solver/verifier prompt slots without intentionally changing verifier/completion semantics. Baseline compatibility remains through SYSTEM_PROMPT and should be retired or quarantined in a later slice, not silently removed here.
- evidence_paths: harness/aether2/runtime/prompts.py; harness/aether2/runtime/run_config.py; harness/aether2/runtime/adaptive_context.py; harness/aether2/runtime/verify.py; harness/aether2/control/ahp_startup.py; harness/aether2/control/ahp_preflight.py; harness/aether2/control/verification_rounds.py; harness/aether2/runtime/__init__.py; tests/test_aether2_prompts.py; tests/test_aether2_run_config.py; docs/AETHER2_SLICE1_PROMPT_OWNERSHIP_FOUNDATION.md
- affected_components: Aether-2 prompt assembly; AHP startup; run config; verifier prompt plumbing; prompt ownership tests; grader wording
- decision_change: Slice 1 is complete. Recommended next slice is Slice 2 Architect Workbench Config And Init Failure.
- unresolved_questions: Whether AHP should be renamed/evolved into Architect or replaced by a WorkbenchArchitect-style surface inside harness/aether2 during Slice 2; exact result-row representation for agent_initialization_failure remains open for Slice 2.
- confidence: high
- commit_message: harness: add architect-owned prompt foundation for Aether-2

Validation:
- `python3 -m pytest -q tests/test_aether2_prompts.py tests/test_aether2_run_config.py` -> 29 passed in 0.38s
- `python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng` -> exit code 0, no output
- `python3 -m pytest -q tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py tests/test_aether2_verification_feedback.py` -> 17 passed in 3.78s
- `make public-tests` -> 11 passed in 0.91s

Note: tracking/ledger/tools/record_update.py is not present in this checkout, so this raw update was persisted directly under tracking/ledger/inbox using the repository's existing raw handoff file pattern.
