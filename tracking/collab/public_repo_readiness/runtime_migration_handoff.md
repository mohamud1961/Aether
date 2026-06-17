# Runtime Migration Handoff

- Status: `COMPLETE`
- Direct parent message: `SENT`
- Date: `2026-06-15`

## Files Changed

- `harness/aether2/runtime/__init__.py`
- `harness/aether2/runtime/bridge_harbor.py`
- `harness/aether2/runtime/context.py`
- `harness/aether2/runtime/executor.py`
- `harness/aether2/runtime/jobs.py`
- `harness/aether2/runtime/model_client.py`
- `harness/aether2/runtime/sessions.py`
- `harness/aether2/__init__.py`
- `runner/aether2/bridge_harbor.py`
- `runner/aether2/context.py`
- `runner/aether2/executor.py`
- `runner/aether2/jobs.py`
- `runner/aether2/model_client.py`
- `runner/aether2/sessions.py`
- `tests/test_aether2_runtime_identity.py`

## Canonical Versus Compatibility Paths

- Canonical runtime implementations now live under `harness/aether2/runtime/`:
  - `bridge_harbor.py`
  - `context.py`
  - `executor.py`
  - `jobs.py`
  - `model_client.py`
  - `sessions.py`
- Legacy `runner.aether2.*` imports for those modules remain available as thin compatibility shims:
  - `runner.aether2.bridge_harbor`
  - `runner.aether2.context`
  - `runner.aether2.executor`
  - `runner.aether2.jobs`
  - `runner.aether2.model_client`
  - `runner.aether2.sessions`
- `harness.aether2.__init__` now re-exports the runtime classes and the existing traces surface from the public `harness` namespace.

## Tests And Commands

- `python3 -m py_compile harness/aether2/runtime/__init__.py harness/aether2/runtime/bridge_harbor.py harness/aether2/runtime/context.py harness/aether2/runtime/executor.py harness/aether2/runtime/jobs.py harness/aether2/runtime/model_client.py harness/aether2/runtime/sessions.py harness/aether2/__init__.py runner/aether2/bridge_harbor.py runner/aether2/context.py runner/aether2/executor.py runner/aether2/jobs.py runner/aether2/model_client.py runner/aether2/sessions.py tests/test_aether2_runtime_identity.py tools/run_aether2_g2.py tools/run_aether2_g3_official.py tools/aether2_genericity_check.py`
- `python3 -m pytest tests/test_aether2_runtime_identity.py tests/test_aether2_bridge_harbor.py tests/test_aether2_executor.py tests/test_aether2_jobs.py tests/test_aether2_model_client.py tests/test_aether2_context.py tests/test_aether2_sessions.py -q -p no:cacheprovider`
  - Result: `50 passed in 5.96s`
- `python3 tools/aether2_genericity_check.py`
  - Result: passed
- `python3 -m pytest tests/test_aether2_*.py tests/test_run_aether2_g2.py tests/test_run_aether2_g3_official.py tests/test_run_aether2_tournament.py -q -p no:cacheprovider`
  - Result: `234 passed in 66.99s`
- Import identity smoke:
  - `runner.aether2.bridge_harbor` == `harness.aether2.runtime.bridge_harbor`
  - `runner.aether2.context` == `harness.aether2.runtime.context`
  - `runner.aether2.executor` == `harness.aether2.runtime.executor`
  - `runner.aether2.jobs` == `harness.aether2.runtime.jobs`
  - `runner.aether2.model_client` == `harness.aether2.runtime.model_client`
  - `runner.aether2.sessions` == `harness.aether2.runtime.sessions`

## Compatibility Guarantees

- Public behavior, serialized outputs, process/job/session semantics, and CLI behavior were left unchanged.
- The old `runner.aether2.*` entry paths now resolve to the same canonical module objects as the new `harness.aether2.runtime.*` paths.
- Module-level monkeypatching continues to work because the runner shims alias `sys.modules[__name__]` to the canonical runtime module objects.
- Foreign-cwd entrypoints remain intact because this slice did not alter the entrypoint bootstrap logic.

## Self-Review Findings

- No import cycles were introduced by the namespace move.
- No dual implementation remains for the six runtime modules; the runner files are alias-only shims now.
- The shim `__all__` surface was checked and preserved for the modules that previously declared one explicitly.
- The direct module identity checks passed for every old/new runtime pair.
- `codex review --uncommitted` could not complete because the local review tool hit a config parse error (`unknown variant 'default', expected 'fast' or 'flex' in service_tier`).
- I did not find any behavior-preserving regression, monkeypatch breakage, or foreign-cwd import failure in the migrated runtime paths.

## Confirmation

- No behavior fixes were intentionally introduced beyond the namespace migration and shim cleanup.
- No Git commits were created.
- No Git pushes were made.
- No eval or full-run evaluation was started.

## Exact Next Recommended Migration Slice

- Migrate the remaining Aether control-plane and environment-adjacent modules into the public `harness/` namespace with the same alias pattern, starting with:
  - `runner/aether2/compactor.py`
  - `runner/aether2/orientation.py`
  - `runner/aether2/metrics.py`
  - `runner/aether2/cleanup_accounting.py`
  - `runner/aether2/prompts.py`
  - `runner/aether2/escalation.py`
  - `runner/aether2/verify.py`
- Keep `runner.aether2.loop` as its own later slice because it is the largest orchestration module and has the densest dependency fan-out.
