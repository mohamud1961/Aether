# Control Plane Migration Handoff

- Final status: `COMPLETE`
- Source thread ID: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Date: `2026-06-15`

## Objective

Complete the next behavior-preserving public-namespace migration slice for the
Aether-2 control plane by moving the canonical loop implementation into the
approved public `harness/aether2/` tree, keeping the legacy `runner/aether2`
path as an alias-only compatibility shim, and only migrating any additional
tightly coupled Aether module when dependency inspection proved it belonged in
the same atomic slice.

## Final Status

`COMPLETE`

The canonical loop implementation now lives at
`harness/aether2/control/loop.py`. The tightly coupled generic tool
schema/dispatch implementation also moved in the same atomic slice to
`harness/aether2/tools/native.py` because the canonical public loop otherwise
would have depended on a legacy `runner.*` implementation. The legacy runner
paths are alias-only shims using the established `sys.modules` pattern.

## Remaining-Module Inventory And Classification

### Pre-Edit Remaining Non-Shim Implementations Under `runner/aether2/`

- `runner/aether2/loop.py`: `control plane`
- `runner/aether2/tools.py`: `public API/entrypoint`, tightly coupled to the
  loop through `TOOL_SCHEMAS` and `dispatch`
- `runner/aether2/__init__.py`: `public API/entrypoint` package aggregator

### Post-Edit `runner/aether2/` Inventory

- `runner/aether2/__init__.py`: `public API/entrypoint`
- `runner/aether2/bridge_harbor.py`: `compatibility-only`
- `runner/aether2/cleanup_accounting.py`: `compatibility-only`
- `runner/aether2/compactor.py`: `compatibility-only`
- `runner/aether2/context.py`: `compatibility-only`
- `runner/aether2/delta.py`: `compatibility-only`
- `runner/aether2/envelope.py`: `compatibility-only`
- `runner/aether2/escalation.py`: `compatibility-only`
- `runner/aether2/executor.py`: `compatibility-only`
- `runner/aether2/jobs.py`: `compatibility-only`
- `runner/aether2/loop.py`: `compatibility-only`
- `runner/aether2/metrics.py`: `compatibility-only`
- `runner/aether2/mirror.py`: `compatibility-only`
- `runner/aether2/model_client.py`: `compatibility-only`
- `runner/aether2/orientation.py`: `compatibility-only`
- `runner/aether2/prompts.py`: `compatibility-only`
- `runner/aether2/receipts.py`: `compatibility-only`
- `runner/aether2/sessions.py`: `compatibility-only`
- `runner/aether2/tools.py`: `compatibility-only`
- `runner/aether2/verify.py`: `compatibility-only`

### Deferred External Dependency Classification

- None inside `runner/aether2/` after this slice.

## Actual Scope Completed

- Moved the canonical implementation of `runner/aether2/loop.py` to
  `harness/aether2/control/loop.py` with import edges updated only where
  required to make the public namespace canonical.
- Moved the tightly coupled canonical implementation of `runner/aether2/tools.py`
  to `harness/aether2/tools/native.py`.
- Replaced `runner/aether2/loop.py` with an alias-only compatibility shim.
- Replaced `runner/aether2/tools.py` with an alias-only compatibility shim.
- Added public package exports for the new canonical surfaces:
  `harness/aether2/control/__init__.py`,
  `harness/aether2/tools/__init__.py`, and `harness/aether2/__init__.py`.
- Added focused identity and foreign-cwd entrypoint coverage in
  `tests/test_aether2_runtime_identity.py` and `tests/test_run_aether2_g2.py`.

## Exact Files Changed

- `harness/aether2/control/__init__.py`
- `harness/aether2/control/loop.py`
- `harness/aether2/tools/__init__.py`
- `harness/aether2/tools/native.py`
- `harness/aether2/__init__.py`
- `runner/aether2/loop.py`
- `runner/aether2/tools.py`
- `tests/test_aether2_runtime_identity.py`
- `tests/test_run_aether2_g2.py`

## Canonical Versus Compatibility Paths

- Canonical loop module: `harness.aether2.control.loop`
- Compatibility loop path: `runner.aether2.loop`
- Canonical tool schema/dispatch module: `harness.aether2.tools.native`
- Public tool package export: `harness.aether2.tools`
- Compatibility tool path: `runner.aether2.tools`
- Public top-level exports updated in: `harness.aether2`

## Loop Import And Importer Mapping

### Loop Imports Mapped Before Editing

- Runtime/control dependencies:
  - `runner.aether2.bridge_harbor`
  - `runner.aether2.compactor`
  - `runner.aether2.context`
  - `runner.aether2.executor`
  - `runner.aether2.jobs`
  - `runner.aether2.orientation`
  - `runner.aether2.prompts`
  - `runner.aether2.sessions`
  - `runner.aether2.verify`
- Trace dependencies:
  - `runner.aether2.delta`
  - `runner.aether2.envelope`
  - `runner.aether2.mirror`
  - `runner.aether2.receipts`
- Tightly coupled public API dependency:
  - `runner.aether2.tools`
- Shared external helper:
  - `runner.kernel_layer2_audit`

### Loop Importers Mapped Before Editing

- `runner/aether2/__init__.py`
- `tools/run_aether2_g2.py`
- `tools/run_aether2_g3_official.py`
- `tests/test_aether2_loop.py`
- `tests/test_aether2_bridge_harbor.py`
- `tests/test_run_aether2_g2.py`

### Dependency-Driven Atomic-Slice Decision

- `runner/aether2/tools.py` moved in the same slice because the loop imports
  `TOOL_SCHEMAS` and `dispatch` directly, and keeping those canonical only in
  `runner.*` would have left the public `harness.aether2.control.loop`
  implementation dependent on a legacy namespace.
- No additional runner module needed to move in this slice because all other
  loop dependencies already pointed at canonical public `harness` modules via
  compatibility shims.

## Requirement-By-Requirement Disposition

1. Map every loop import and every importer before editing.
   - `DONE`. Mapped the loop import graph and importers listed above before
     making file moves.
2. Select and document the canonical public location.
   - `DONE`. Canonical locations selected from the approved public tree:
     `harness/aether2/control/loop.py` and the tightly coupled
     `harness/aether2/tools/native.py`.
3. Move the canonical implementation without semantic edits.
   - `DONE`. `loop.py` and `tools.py` were moved with only namespace import
     rewrites and package-export plumbing.
4. Replace the legacy path with the proven `sys.modules` module-alias pattern
   where identity matters.
   - `DONE`. `runner/aether2/loop.py` and `runner/aether2/tools.py` are
     alias-only shims that set `sys.modules[__name__]` to the canonical module.
5. Update only import edges necessary to establish canonical ownership.
   - `DONE`. Import changes were limited to the moved canonical modules and
     `harness/aether2/__init__.py`.
6. Add tests proving old/new module identity, public-object identity,
   monkeypatch sharing, and unchanged entrypoint behavior.
   - `DONE`. Added module/object identity and monkeypatch sharing assertions in
     `tests/test_aether2_runtime_identity.py` plus foreign-cwd entrypoint import
     coverage in `tests/test_run_aether2_g2.py`.
7. Verify foreign-cwd imports and entrypoints remain functional.
   - `DONE`. The new G2 foreign-cwd module-load test passed, and the existing G3
     foreign-cwd help test remained green in the focused and broad suites.
8. Inspect for circular imports introduced by the public package exports.
   - `DONE`. Import smoke and full test passes confirmed no circular import
     failure from `harness.aether2`, `harness.aether2.control`, or
     `harness.aether2.tools`.

## Exact Commands And Results

### Import Identity Smoke

- `python3 - <<'PY' ...`
  - Result:
    - `runner.aether2.loop True harness.aether2.control.loop`
    - `runner.aether2.tools True harness.aether2.tools.native`
    - `harness.aether2.control.loop`
    - `harness.aether2.tools.native`

### Syntax / Diff Hygiene

- `python3 -m py_compile harness/aether2/control/__init__.py harness/aether2/control/loop.py harness/aether2/tools/__init__.py harness/aether2/tools/native.py harness/aether2/__init__.py runner/aether2/loop.py runner/aether2/tools.py tests/test_aether2_runtime_identity.py tests/test_run_aether2_g2.py`
  - Result: passed

- `git diff --check -- harness/aether2/control/__init__.py harness/aether2/control/loop.py harness/aether2/tools/__init__.py harness/aether2/tools/native.py harness/aether2/__init__.py runner/aether2/loop.py runner/aether2/tools.py tests/test_aether2_runtime_identity.py tests/test_run_aether2_g2.py`
  - Result: passed

### Focused Tests

- `python3 -m pytest tests/test_aether2_runtime_identity.py tests/test_aether2_loop.py tests/test_aether2_tools.py tests/test_aether2_bridge_harbor.py tests/test_run_aether2_g2.py tests/test_run_aether2_g3_official.py -q -p no:cacheprovider`
  - Result: `86 passed in 55.49s`

### Genericity Gate

- `python3 tools/aether2_genericity_check.py`
  - Result: passed

### Exact Broad Baseline

- `python3 -m pytest tests/test_aether2_*.py tests/test_run_aether2_g2.py tests/test_run_aether2_g3_official.py tests/test_run_aether2_tournament.py -q -p no:cacheprovider`
  - Result: `236 passed in 66.70s (0:01:06)`

### Ordering / State Leakage Repeat

- `python3 -m pytest tests/test_aether2_*.py tests/test_run_aether2_g2.py tests/test_run_aether2_g3_official.py tests/test_run_aether2_tournament.py -q -p no:cacheprovider`
  - Result: `236 passed in 66.07s (0:01:06)`

## Compatibility And Behavior-Preservation Evidence

- `runner.aether2.loop` and `harness.aether2.control.loop` resolve to the same
  live module object.
- `runner.aether2.tools` and `harness.aether2.tools.native` resolve to the same
  live module object.
- `runner.aether2.run_aether2_loop` and `harness.aether2.run_aether2_loop`
  resolve to the same function object, with canonical module name
  `harness.aether2.control.loop`.
- `runner.aether2.dispatch` and `harness.aether2.dispatch` resolve to the same
  function object, with canonical module name
  `harness.aether2.tools.native`.
- Monkeypatch sharing was proven by mutating `STEP_CAP` through the runner loop
  path and `dispatch` through the canonical tool path and observing the same
  module state through the opposite import path.
- The G2 entrypoint module now loads from a foreign cwd without `PYTHONPATH`
  while exposing the canonical loop module, and the existing G3 foreign-cwd
  entrypoint help test remained green.
- The exact broad Aether test subset passed twice, which did not reveal import
  ordering or state leakage.

## Code Review And Adversarial Findings

### Codex Review Helper

- Attempted command:
  `~/.codex/skills/codex-review/scripts/codex-review --mode local`
- Result: blocked
- Exact error:
  `Error loading config.toml: unknown variant \`default\`, expected \`fast\` or \`flex\` in service_tier`

### Manual Adversarial Review Coverage

Reviewed the live source and test evidence for:

- semantic drift from the move;
- alias/module identity;
- monkeypatch sharing;
- circular imports from `harness.aether2` package exports;
- mutable module-global sharing;
- entrypoint bootstrap behavior from foreign cwd;
- serialization/tool schema stability;
- prompt stability;
- duplicate implementations and stale old code;
- unrelated changes.

### Findings And Dispositions

- Finding: `runner/aether2/tools.py` belonged in the same slice as `loop.py`
  because the loop imports `TOOL_SCHEMAS` and `dispatch` directly.
  - Disposition: `ACCEPTED` and fixed by moving the canonical implementation to
    `harness/aether2/tools/native.py`.
- Finding: The new G2 foreign-cwd smoke initially embedded a `Path` repr that
  would have produced `PosixPath(...)` inside the subprocess.
  - Disposition: `ACCEPTED` and fixed by embedding `str(script_path)` instead.
- Finding: No remaining actionable defects found after the fixes above.
  - Disposition: `REJECTED AS NO FURTHER ACTION REQUIRED`

## Unresolved Risks And Exact Next Dependency-Ready Action

- Unresolved risk: the Codex review helper remains blocked by the local
  `service_tier` config parse issue, so future `codex_review_skill*` closeouts
  still need either the same manual adversarial fallback or an environment fix.
- No behavior, import-identity, or ordering/state-leakage regression was found
  in this slice.
- Exact next dependency-ready action:
  - Keep `runner/aether2/__init__.py` as the stable compatibility aggregator for
    now.
  - If the publication program continues, evaluate whether a later dedicated
    public-API cleanup slice should migrate or thin the package-level aggregator
    once orchestrator-approved import consumers are ready.

## External State And Prohibited Actions Confirmation

- No Git branch was created.
- No worktree was created.
- No commit was created.
- No push was performed.
- No eval or full task run was started.
- No latest-run behavior fix was introduced.
- No persistent process, container, VM, server, or credential home was started
  or left active for this task.

## Persisted RAW Ledger Update

- `tracking/ledger/inbox/2026-06-15/180429_compatibility-migration-worker-4_aether-2-control-plane-public-namespace-migration-slice_57bd7bed50.md`

## Thread Send

- Target thread ID: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Authoritative file verification command:
  `ls -l tracking/collab/public_repo_readiness/control_plane_migration_handoff.md`
- Authoritative file verification result:
  `-rw-r--r--@ 1 mohamud  staff  13189 Jun 15 19:05 tracking/collab/public_repo_readiness/control_plane_migration_handoff.md`
- Corrected post-persistence send tool used: `codex_app.send_message_to_thread`
- Corrected post-persistence send result: success
- Corrected returned payload: `{"threadId":"019eb760-ea75-7af1-8d62-6e3e8cd7ba2a"}`
- Tool used: `codex_app.send_message_to_thread`
- Tool result: success
- Returned payload: `{"threadId":"019eb760-ea75-7af1-8d62-6e3e8cd7ba2a"}`
