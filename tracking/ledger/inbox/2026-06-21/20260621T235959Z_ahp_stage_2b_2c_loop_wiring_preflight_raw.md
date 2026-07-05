# RAW_LEDGER_UPDATE: AHP Stage 2B + 2C — Loop Wiring & Preflight

**Date:** 2026-06-21
**Stage:** AHP 2B (loop wiring) + 2C (preflight)
**Status:** COMPLETE — 42/42 preflight checks pass, 151/151 pytest pass, genericity clean

## What was done

### Stage 2B: Loop Wiring
- Wired `adaptive_context.py` (existing adapter) into `loop.py` via flag-gated startup phase
- Flag: `adaptive_profile_enabled` (default=False) on `run_aether2_loop()`
- Insertion: between `orient()` and `build_prefix()`, data-driven adapter only, no task-specific branches
- Authority-level wiring:
  - `hard_visible_requirements` -> `completion_contract`
  - `inferred_success_requirements` -> verifier `stated_requirements` (tagged `[inferred]`)
  - `verification_watchpoints` -> verifier focus
  - `do_not_assume` -> verifier + solver anti-invention guidance
  - `selected_tools` -> exposed tool schema subset (unselected hidden)
  - `initial_plan` -> solver-visible checklist (revisable)
  - `solver_system_prompt` -> task block appended AFTER stable invariant kernel
- Prefix order: [stable invariant kernel] -> [task block] -> [task instruction] -> [orientation] -> [tool schemas] -> [extra prefix messages incl. profile summary + initial plan]
- Artifacts written per-run to `.aether2/ahp/`

### Refinement 1: Neutral Wording
- Renamed `likely_failure_modes` -> `approach_risks` everywhere (schema, validator, adapter, fallback, meta-prompt)
- No benchmark-implying language remains (verified by preflight neutral wording checks)

### Refinement 2: initial_plan
- Added `initial_plan` field to contract schema, meta-prompt, fallback profile, ValidatedRunConfig, adapter
- Renders as solver-visible checklist with explicit "a starting guide, not a script" note
- Capped at 5 steps, each `{step, status, evidence_needed}`

### Stage 2C: Preflight
- 42/42 checks pass exercising real data paths (not just imports)
- Flag-off baseline byte-identical (prefix digest, frozen bytes, tool schema digest all match)
- Flag-on: contract validates, fallback works, task block after kernel, tools filtered, authority mapping correct, artifacts written, initial plan renders

## Files Changed
- `harness/aether2/control/loop.py` — added import + flag param + 32-line AHP startup insertion
- `harness/aether2/control/ahp_startup.py` — NEW: startup phase entry point (141 LOC)
- `harness/aether2/control/ahp_preflight.py` — NEW: Stage 2C preflight script (546 LOC)
- `harness/aether2/runtime/adaptive_context.py` — added initial_plan, extracted write_ahp_artifacts, removed unused imports (410 LOC)
- `harness/aether2/runtime/adaptive_artifacts.py` — NEW: extracted artifact writer with authority_mapping + verifier_payload_preview (112 LOC)
- `harness/aether2/runtime/adaptive_profile.py` — renamed likely_failure_modes -> approach_risks, added initial_plan to schema (496 LOC)
- `harness/aether2/runtime/adaptive_profile_helpers.py` — renamed field + added initial_plan to fallback (195 LOC)

## Evidence
- pytest: 151 passed, 0 failed
- genericity check: clean (exit 0)
- preflight: 42/42 pass
- flag-off baseline: prefix digest ceae404274f021a0... identical
- no benchmark/grader/hidden-test framing in model-visible prompts

## Out of Scope (per spec)
- Stage 2D: solve-rate A/B
- Spec compiler, generated executable checks
- Expanded repeat detection
- Full amendment/pivot system
- Model-configured compaction enforcement

## BLOCKED Items
- None
