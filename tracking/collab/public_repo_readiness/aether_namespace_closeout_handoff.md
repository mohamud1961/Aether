# Aether Namespace Closeout Handoff

- Status: `COMPLETE`
- Source thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Date: `2026-06-15`

## Summary

The Aether-2 namespace migration is closed for the `runner.aether2` compatibility layer.

- Every legacy `runner/aether2/*.py` implementation now has exactly one canonical public home.
- All non-`__init__.py` legacy modules are identity-preserving alias shims.
- `runner.aether2` remains a stable compatibility package, but its top-level aggregator now imports canonical `harness` objects directly.
- The only remaining legacy-adjacent imports are external shared helpers outside the Aether namespace: `runner.model_client` and `runner.kernel_layer2_audit`.

## Complete Old-To-Canonical Map

| Legacy module | Classification | Canonical home |
| --- | --- | --- |
| `runner.aether2.__init__` | package aggregator | `harness.aether2` and its canonical subpackages |
| `runner.aether2.bridge_harbor` | true alias-only shim | `harness.aether2.runtime.bridge_harbor` |
| `runner.aether2.cleanup_accounting` | true alias-only shim | `harness.aether2.runtime.cleanup_accounting` |
| `runner.aether2.compactor` | true alias-only shim | `harness.aether2.runtime.compactor` |
| `runner.aether2.context` | true alias-only shim | `harness.aether2.runtime.context` |
| `runner.aether2.delta` | true alias-only shim | `harness.aether2.traces.delta` |
| `runner.aether2.envelope` | true alias-only shim | `harness.aether2.traces.envelope` |
| `runner.aether2.escalation` | true alias-only shim | `harness.aether2.runtime.escalation` |
| `runner.aether2.executor` | true alias-only shim | `harness.aether2.runtime.executor` |
| `runner.aether2.jobs` | true alias-only shim | `harness.aether2.runtime.jobs` |
| `runner.aether2.loop` | true alias-only shim | `harness.aether2.control.loop` |
| `runner.aether2.metrics` | true alias-only shim | `harness.aether2.runtime.metrics` |
| `runner.aether2.mirror` | true alias-only shim | `harness.aether2.traces.mirror` |
| `runner.aether2.model_client` | true alias-only shim | `harness.aether2.runtime.model_client` |
| `runner.aether2.orientation` | true alias-only shim | `harness.aether2.runtime.orientation` |
| `runner.aether2.prompts` | true alias-only shim | `harness.aether2.runtime.prompts` |
| `runner.aether2.receipts` | true alias-only shim | `harness.aether2.traces.receipts` |
| `runner.aether2.sessions` | true alias-only shim | `harness.aether2.runtime.sessions` |
| `runner.aether2.tools` | true alias-only shim | `harness.aether2.tools.native` |
| `runner.aether2.verify` | true alias-only shim | `harness.aether2.runtime.verify` |

## Discrepancies Versus Prior Handoffs

- Prior handoffs correctly identified the canonical homes for traces, runtime, runtime-support, and control-plane slices.
- The orchestrator’s exact-pattern scan flagged `bridge_harbor.py`, `context.py`, `delta.py`, `envelope.py`, `executor.py`, `jobs.py`, `mirror.py`, `model_client.py`, `receipts.py`, and `sessions.py` as apparently live. Source review and identity checks showed those files are alias-only shims, not duplicate implementations.
- `runner.aether2.__init__.py` still imported from `runner.aether2.*` before this closeout. I normalized it to canonical `harness` imports so the compatibility package no longer depends on its own shims.
- The existing executor/jobs test scaffolding leaked a `runner.aether2.verify` stub into later imports. That was a test-harness issue, not a migration issue, and it was removed.

## Exact Files Changed

- `runner/aether2/__init__.py`
- `tests/test_aether2_runtime_identity.py`
- `tests/test_aether2_executor.py`
- `tests/test_aether2_jobs.py`
- `tracking/collab/public_repo_readiness/aether_namespace_closeout_map.md`
- `tracking/ledger/inbox/2026-06-15/181812_compatibility-migration-worker-5_aether-namespace-public-api-and-compatibility-closeout_1a82a4f5bd.md`

## Requirement Dispositions

1. Build a complete old-to-canonical module map for every `runner/aether2/*.py` file.
   - `DONE`
2. Classify each legacy file.
   - `DONE`
3. Move any duplicate/live implementation into `harness/aether2/{control,runtime,tools,traces}` and replace the legacy file with an identity-preserving alias.
   - `DONE`
4. Preserve `runner.aether2` as a stable compatibility package.
   - `DONE`
5. Audit internal production imports so canonical `harness` code does not depend on legacy `runner.aether2.*`.
   - `DONE` for the Aether namespace. Remaining `runner.model_client` and `runner.kernel_layer2_audit` references are external shared helpers, not Aether namespace dependencies.
6. Add comprehensive tests for module identity, package identity, monkeypatch sharing, import order, foreign cwd, and duplicate-implementation absence.
   - `DONE`
7. Produce a machine-readable or markdown compatibility map.
   - `DONE`
8. Close out with validation and adversarial review evidence.
   - `DONE` with one test-scaffolding fix applied after the first broad baseline exposed a leaked verify stub.

## Validation Results

- `python3 -m py_compile $(rg --files harness/aether2 runner/aether2 tests tools | rg '\\.py$')`
  - Result: passed
- `python3 tools/aether2_genericity_check.py`
  - Result: passed
- `python3 -m pytest tests/test_aether2_runtime_identity.py tests/test_aether2_entrypoint_import_hygiene.py tests/test_aether2_tools.py -q -p no:cacheprovider`
  - Result: `27 passed in 9.04s`
- `python3 -m pytest tests/test_aether2_executor.py tests/test_aether2_jobs.py tests/test_aether2_verify.py -q -p no:cacheprovider`
  - Result: `30 passed in 1.44s`
- Broad baseline run 1:
  - `python3 -m pytest tests/test_aether2_*.py tests/test_run_aether2_g2.py tests/test_run_aether2_g3_official.py tests/test_run_aether2_tournament.py -q -p no:cacheprovider`
  - Result: `239 passed in 69.96s`
- Broad baseline run 2:
  - `python3 -m pytest tests/test_aether2_*.py tests/test_run_aether2_g2.py tests/test_run_aether2_g3_official.py tests/test_run_aether2_tournament.py -q -p no:cacheprovider`
  - Result: `239 passed in 67.32s`
- Diff hygiene:
  - `git diff --no-index --check /dev/null <owned-file>` checks for the owned files produced no whitespace warnings.

## Review Findings And Fixes Or Rebuttals

- Codex review helper attempt:
  - `~/.codex/skills/codex-review/scripts/codex-review --mode local`
  - Result: blocked by local config parse error: `unknown variant 'default', expected 'fast' or 'flex' in service_tier`
- Manual adversarial review covered:
  - duplicate live implementations;
  - alias vs identity-preserving shim behavior;
  - package import order;
  - monkeypatch sharing;
  - circular imports;
  - public API drift;
  - foreign-cwd behavior;
  - stale legacy dependencies.
- Accepted finding:
  - The executor/jobs tests were leaking a `runner.aether2.verify` stub into later imports. I removed the stub entirely because those modules do not need it.
- Rebuttals:
  - The apparent live legacy modules from the exact-pattern scan are true alias shims, not duplicate implementations.
  - The runner package aggregator now imports canonical modules directly, so the compatibility package is stable without depending on its own legacy shims.
- No other accepted adversarial findings remained after the final validation rerun.

## Remaining External Legacy Dependencies

- `runner.model_client` in `harness/aether2/runtime/model_client.py`
- `runner.kernel_layer2_audit` in `harness/aether2/control/loop.py` and `harness/aether2/runtime/verify.py`

These are outside the Aether namespace and were intentionally retained because no approved public home exists in this slice.

## Closure State

- Aether namespace migration fully closed: `YES`
- Remaining legacy Aether modules: none beyond compatibility shims
- Remaining external state active: none

## Exact Next Dependency-Ready Publication Step

- Hand the compatibility map and this closeout to the historian/ledger flow, then proceed to the next public-repo publication slice for documentation and packaging curation.

## External-State Confirmation

- No branch, worktree, commit, or push was created.
- No process, container, VM, server, or credential home was left running for this task.
- The Codex review helper remained blocked by the local `service_tier` config issue; no additional external state was introduced.

## Thread Send

- Target thread ID: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Send tool result: success (`codex_app.send_message_to_thread` returned `{"threadId":"019eb760-ea75-7af1-8d62-6e3e8cd7ba2a"}`)
