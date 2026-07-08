# Aether-2 Slice 6 Config Surface Cleanup

Status: completed

Date: 2026-07-02

## Purpose

Slice 6 ensures architect-exposed config fields are either realized or rejected clearly. The architect can design the workbench, but the harness must not silently ignore fake knobs that imply authority the architect does not actually have.

## Adds

- Strict unsupported-field validation for architect profile config:
  - unsupported top-level profile fields;
  - unsupported `tool_configuration` fields;
  - unsupported `context_configuration` fields;
  - unsupported `compaction_recommendation` fields;
  - unsupported `verification_configuration` fields.
- `config_realization_audit.json` AHP artifact.
- `build_config_realization_audit(...)` for tests and artifact writing.
- Tests proving unsupported `tool_policy`, `helper_script_policy`, fake tool-routing fields, and mutation verifier fields fail clearly.
- Tests proving the realization audit lists realized surfaces and rejected/unsupported warnings.

## Changes

- `validate_profile` now rejects unsupported architect config surfaces instead of silently ignoring them.
- `write_ahp_artifacts` now emits `config_realization_audit.json`.
- Realized config mapping is explicit for prompts, context policy, tool selection metadata, hard/inferred requirements, verifier focus/system prompt, final evidence, repeat guidance, initial plan, and compaction preferences.

## Deletes

- No files were deleted in this slice.
- The silent-ignore behavior for unsupported architect config fields was removed.

## Deferred

- No new tool capability was added.
- Solver tools remain harness-owned stable capabilities after architect selection/filtering.
- Verifier capabilities remain within the generic read-only verifier tool set.
- Historical duplicate judgement paths are deferred to Slice 7.

## Tests

Passed:

```bash
python3 -m pytest -q tests/test_aether2_run_config.py tests/test_aether2_prompts.py
```

Result: 33 passed in 0.49s

Passed:

```bash
python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng
```

Result: exit 0, no output

Passed:

```bash
python3 -m pytest -q tests/test_aether2_prompts.py tests/test_aether2_run_config.py tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py tests/test_aether2_verification_feedback.py tests/test_compaction_receipt_continuity.py tests/test_aether2_compactor.py tests/test_aether2_transcript_repair.py tests/test_aether2_hooks.py tests/test_aether2_post_upgrade_behaviors.py
```

Result: 96 passed in 57.27s

Passed:

```bash
python3 -m pytest -q tests/test_run_custom_eval_board.py
```

Result: 56 passed in 31.28s

Passed:

```bash
make public-tests
```

Result: 11 passed in 0.83s

## Risk

- Strict validation can reject old stored/generated profiles that contained unused extra fields.
- The compatibility path is now "reject and repair once," not "accept and ignore"; this is intentional for certified runs but may surface more initialization failures during debugging.
- The realization audit is static mapping plus current config values; it is not a proof that downstream runtime behavior executed in a particular run.

## Rollback

Revert the strict unsupported-field checks, `config_realization_audit.json` emission, and associated tests. That would restore compatibility with profiles containing ignored fields, but would also reintroduce fake config surfaces.
