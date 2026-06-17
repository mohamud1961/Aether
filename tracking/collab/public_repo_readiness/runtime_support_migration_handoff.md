# Runtime Support Migration Handoff

- Status: `COMPLETE`
- Date: `2026-06-15`
- Source thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`

## Objective And Scope

Moved the canonical implementations of the Aether-2 runtime support modules into the public `harness/aether2/runtime/` tree and kept the old `runner/aether2/` paths working through thin compatibility aliases.

Modules covered:

- `compactor.py`
- `orientation.py`
- `metrics.py`
- `cleanup_accounting.py`
- `prompts.py`
- `escalation.py`
- `verify.py`

Out of scope and not changed:

- `runner/aether2/loop.py`
- eval runs
- behavioral fixes or semantic rewrites
- branch creation, commits, pushes, persistent processes, containers, VMs, or credential homes

## Files Changed

Canonical modules:

- `harness/aether2/runtime/compactor.py`
- `harness/aether2/runtime/orientation.py`
- `harness/aether2/runtime/metrics.py`
- `harness/aether2/runtime/cleanup_accounting.py`
- `harness/aether2/runtime/prompts.py`
- `harness/aether2/runtime/escalation.py`
- `harness/aether2/runtime/verify.py`

Compatibility aliases:

- `runner/aether2/compactor.py`
- `runner/aether2/orientation.py`
- `runner/aether2/metrics.py`
- `runner/aether2/cleanup_accounting.py`
- `runner/aether2/prompts.py`
- `runner/aether2/escalation.py`
- `runner/aether2/verify.py`

Package exports and tests:

- `harness/aether2/runtime/__init__.py`
- `tests/test_aether2_runtime_identity.py`
- `tests/test_aether2_orientation.py`

## Canonical And Compatibility Paths

Canonical implementations now live at:

- `harness.aether2.runtime.compactor`
- `harness.aether2.runtime.orientation`
- `harness.aether2.runtime.metrics`
- `harness.aether2.runtime.cleanup_accounting`
- `harness.aether2.runtime.prompts`
- `harness.aether2.runtime.escalation`
- `harness.aether2.runtime.verify`

Legacy compatibility paths remain available and resolve to the same module objects:

- `runner.aether2.compactor`
- `runner.aether2.orientation`
- `runner.aether2.metrics`
- `runner.aether2.cleanup_accounting`
- `runner.aether2.prompts`
- `runner.aether2.escalation`
- `runner.aether2.verify`

## Per-Module Disposition

- `compactor.py`: canonical copy moved to `harness/aether2/runtime/compactor.py`; runner path is an alias-only shim; import edges now point at public runtime/traces modules.
- `orientation.py`: canonical copy moved to `harness/aether2/runtime/orientation.py`; runner path is an alias-only shim; behavior and probe order unchanged.
- `metrics.py`: canonical copy moved to `harness/aether2/runtime/metrics.py`; runner path is an alias-only shim; still uses the existing `runner.action_bus` helper because no public twin exists in this slice.
- `cleanup_accounting.py`: canonical copy moved to `harness/aether2/runtime/cleanup_accounting.py`; runner path is an alias-only shim; accounting semantics unchanged.
- `prompts.py`: canonical copy moved to `harness/aether2/runtime/prompts.py`; runner path is an alias-only shim; prompt text unchanged.
- `escalation.py`: canonical copy moved to `harness/aether2/runtime/escalation.py`; runner path is an alias-only shim; decision semantics unchanged.
- `verify.py`: canonical copy moved to `harness/aether2/runtime/verify.py`; runner path is an alias-only shim; verifier parsing and replay behavior unchanged.

## Validation

### Syntax And Import Checks

- `python3 -m py_compile harness/aether2/runtime/__init__.py harness/aether2/runtime/compactor.py harness/aether2/runtime/orientation.py harness/aether2/runtime/metrics.py harness/aether2/runtime/cleanup_accounting.py harness/aether2/runtime/prompts.py harness/aether2/runtime/escalation.py harness/aether2/runtime/verify.py runner/aether2/compactor.py runner/aether2/orientation.py runner/aether2/metrics.py runner/aether2/cleanup_accounting.py runner/aether2/prompts.py runner/aether2/escalation.py runner/aether2/verify.py tests/test_aether2_runtime_identity.py tests/test_aether2_orientation.py`
  - Result: passed

- Import-identity smoke for all seven pairs:
  - `runner.aether2.cleanup_accounting` vs `harness.aether2.runtime.cleanup_accounting`
  - `runner.aether2.compactor` vs `harness.aether2.runtime.compactor`
  - `runner.aether2.escalation` vs `harness.aether2.runtime.escalation`
  - `runner.aether2.metrics` vs `harness.aether2.runtime.metrics`
  - `runner.aether2.orientation` vs `harness.aether2.runtime.orientation`
  - `runner.aether2.prompts` vs `harness.aether2.runtime.prompts`
  - `runner.aether2.verify` vs `harness.aether2.runtime.verify`
  - Result: all pairs resolved to the same module object

- `git diff --check -- harness/aether2/runtime/__init__.py harness/aether2/runtime/compactor.py harness/aether2/runtime/orientation.py harness/aether2/runtime/metrics.py harness/aether2/runtime/cleanup_accounting.py harness/aether2/runtime/prompts.py harness/aether2/runtime/escalation.py harness/aether2/runtime/verify.py runner/aether2/compactor.py runner/aether2/orientation.py runner/aether2/metrics.py runner/aether2/cleanup_accounting.py runner/aether2/prompts.py runner/aether2/escalation.py runner/aether2/verify.py tests/test_aether2_runtime_identity.py tests/test_aether2_orientation.py`
  - Result: passed

### Focused Tests

- `python3 -m pytest tests/test_aether2_runtime_identity.py tests/test_aether2_compactor.py tests/test_aether2_orientation.py tests/test_aether2_metrics.py tests/test_aether2_cleanup_accounting.py tests/test_aether2_prompts.py tests/test_aether2_escalation.py tests/test_aether2_verify.py tests/test_aether2_loop.py tests/test_aether2_context.py tests/test_aether2_receipts.py tests/test_aether2_bridge_harbor.py -q -p no:cacheprovider`
  - Result: `100 passed in 53.24s`

- `python3 tools/aether2_genericity_check.py`
  - Result: passed

- `python3 -m pytest tests/test_aether2_*.py tests/test_run_aether2_g2.py tests/test_run_aether2_g3_official.py tests/test_run_aether2_tournament.py -q -p no:cacheprovider`
  - Result: `234 passed in 65.68s`

## Compatibility Guarantees

- Old and new import paths resolve to the same module objects for all seven migrated modules.
- Monkeypatching works through either path because the runner shims alias `sys.modules[__name__]` to the canonical public module.
- Public object identity is preserved for the runtime exports exercised in the tests.
- Foreign-cwd behavior was not changed in this slice.
- No serialized structures, constants, prompt text, verification semantics, or cleanup/accounting behavior were intentionally changed.

## Adversarial Review

### Automated Helper

- Attempted command: `~/.codex/skills/codex-review/scripts/codex-review --mode local`
- Result: blocked by environment config parse error
- Exact error: `unknown variant \`default\`, expected \`fast\` or \`flex\` in service_tier`

### Manual Source Review

Checked the actual diff for:

- import cycles;
- module identity;
- monkeypatch behavior;
- mutable module state;
- duplicate implementation leftovers;
- foreign-cwd behavior;
- semantic drift;
- unrelated edits.

Findings:

- No accepted defects found.
- The compatibility shims are alias-only.
- The canonical modules execute from the public `harness/` tree.
- The one visible module-path expectation that changed was updated in the test suite to match the new canonical module name.

## RAW Ledger

- Persisted raw historian input: `tracking/ledger/inbox/2026-06-15/173446_compatibility-migration-worker-3_runtime-support-namespace-migration-for-public-harness-aether2-tree_07d6bc7192.md`

## Unresolved Risks

- The Codex review helper remains blocked by the local config issue above.

## Exact Next Action

- No further action is required for this slice.
- If the namespace migration program continues, the next slice should target the remaining control-plane/public API modules under `runner/aether2/` in the same alias-preserving style.

## Confirmation

- No behavior fix was introduced beyond the namespace move.
- No eval run was started.
- No Git commit was created.
- No Git push was made.
- No persistent process, container, VM, or credential home was started or left active for this task.

## Thread Send

- Target thread ID: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Send tool result: success (`codex_app.send_message_to_thread` returned the same `threadId` without error)
