# Raw Ledger Update

- recorded_at_utc: 2026-06-15T18:04:29.693749+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Compatibility Migration Worker 4
- task: Aether-2 control plane public-namespace migration slice
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 57bd7bed50c93981fde84105ae575004263f19e550a60d547c5118aed8a3fee9
- commit_message: HOLD - delegated migration slice with no commit requested
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-15/180429_compatibility-migration-worker-4_aether-2-control-plane-public-namespace-migration-slice_57bd7bed50.md

```text
RAW_LEDGER_UPDATE
- actor: Compatibility Migration Worker 4
- task: Aether-2 control plane public-namespace migration slice
- event_type: implementation
- summary: Moved the canonical Aether-2 loop implementation into harness/aether2/control/loop.py, moved the tightly coupled tool schema/dispatch module into harness/aether2/tools/native.py, and converted the runner loop/tools paths into alias-only compatibility shims.
- observations: Exact import-identity smoke showed runner.aether2.loop == harness.aether2.control.loop and runner.aether2.tools == harness.aether2.tools.native. Focused control-plane tests passed (86 passed). The exact broad Aether baseline passed twice (236 passed, then 236 passed again). The codex-review helper remained blocked by the local service_tier config parse error.
- inference: This slice completes the remaining runner-side control-plane implementation move without behavior drift, preserves monkeypatch/module identity across old and new imports, and leaves runner/aether2/__init__.py as the only non-shim runner package aggregator.
- evidence_paths: harness/aether2/control/loop.py; harness/aether2/tools/native.py; runner/aether2/loop.py; runner/aether2/tools.py; harness/aether2/__init__.py; tests/test_aether2_runtime_identity.py; tests/test_run_aether2_g2.py; tracking/collab/public_repo_readiness/control_plane_migration_handoff.md
- affected_components: runner/aether2; harness/aether2/control; harness/aether2/tools; Aether-2 public package exports; Aether-2 identity/entrypoint tests
- decision_change: The control-plane loop now has canonical ownership under harness/aether2/control, and the tool schema/dispatch helper moves with it as the required tightly coupled public companion module.
- unresolved_questions: The codex-review helper config issue is still unresolved. The remaining runner/aether2 package-level aggregator can stay as a compatibility surface until a later public-API cleanup slice decides whether and how to retire it.
- confidence: high
- commit_message: HOLD - delegated migration slice with no commit requested
```
