# Aether-2 Slice 1 Prompt Ownership Foundation

Status: Slice 1 complete.

Date: 2026-07-02T18:27:30Z

Goal: make architect-authored solver/verifier prompts the substantive
task-specific prompt surfaces while preserving harness-owned mechanical
contracts.

## Scope

Runtime code changed:

- `harness/aether2/runtime/prompts.py`
- `harness/aether2/runtime/run_config.py`
- `harness/aether2/runtime/adaptive_context.py`
- `harness/aether2/runtime/verify.py`
- `harness/aether2/control/ahp_startup.py`
- `harness/aether2/control/ahp_preflight.py`
- `harness/aether2/control/verification_rounds.py`
- `harness/aether2/runtime/__init__.py`

Tests changed:

- `tests/test_aether2_prompts.py`
- `tests/test_aether2_run_config.py`

No verifier/completion semantics were intentionally changed in this slice.

## Slice Contract

Adds:

- `MECHANICAL_SYSTEM_PROMPT`, a harness-owned mechanical frame for tool/action
  schema, safety, runtime invariants, and grader separation.
- `VerifierPolicy.system_prompt` plus `HarnessRunConfig.verifier_system_prompt`.
- architect verifier prompt plumbing into `verify_fresh_context`.
- focused tests proving architect solver/verifier prompt ownership.

Changes:

- AHP startup now uses `MECHANICAL_SYSTEM_PROMPT` as the base system prompt and
  elevates the generated solver prompt into `[architect_solver_prompt]`.
- The legacy `SYSTEM_PROMPT` remains available for baseline compatibility but
  no longer competes with architect-authored solver prompts in the AHP path.
- Prompt wording now says the official grader evaluates after agent
  termination.
- AHP preflight flag-on checks now assert the new ownership model.

Deletes:

- deleted old prompt authority in the AHP path where the large static behavioral
  `SYSTEM_PROMPT` competed with the generated solver prompt.
- deleted old "grader decides" wording from `SYSTEM_PROMPT`.

Deferred:

- full removal of the legacy baseline `SYSTEM_PROMPT`.
- architect config/init failure semantics.
- context/tool-output invariant work.
- verifier loop semantics and completion authority carve-down.

Tests:

- `python3 -m pytest -q tests/test_aether2_prompts.py tests/test_aether2_run_config.py`
  -> `29 passed in 0.38s`
- `python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng`
  -> exit code 0, no output
- `python3 -m pytest -q tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py tests/test_aether2_verification_feedback.py`
  -> `17 passed in 3.78s`
- `make public-tests`
  -> `11 passed in 0.91s`

Risk:

- baseline compatibility still depends on the legacy `SYSTEM_PROMPT`; later
  slices must retire or quarantine it deliberately.
- verifier prompt plumbing is now present, but Slice 4 still owns verifier loop
  behavior and read-only budget semantics.
- several touched files were already dirty or untracked in this checkout, so
  future commit slicing should inspect live diffs carefully.

Rollback:

- restore AHP startup to use `SYSTEM_PROMPT` and `use_full_generated_prompt`
  gating.
- remove `MECHANICAL_SYSTEM_PROMPT` and verifier prompt slots if prompt
  ownership tests reveal regression.
- keep the "official grader evaluates" wording unless separately proven
  harmful.

## Next Slice

Recommended next slice: Slice 2, Architect Workbench Config And Init Failure.

Slice 2 should decide whether AHP evolves into the Architect or is replaced by a
WorkbenchArchitect-style surface inside `harness/aether2/`. It should implement
one malformed/schema-invalid repair retry and classify repeated failure as
`agent_initialization_failure` without certified silent fallback.

