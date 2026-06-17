# Raw Ledger Update

- recorded_at_utc: 2026-06-15T20:15:14.696950+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Direct Claude-TS-to-Python Port Worker 9A
- task: Direct TS-to-Python hooks + permissions substrate port from quarantined claude-code_ts_release into Aether-2
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 6d14a8445f18f56fc389136a430854e2af02b28e9c3913f5650be1c3587084c4
- commit_message: HOLD - direct TS hooks and permissions port slice remains uncommitted
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-15/201514_direct-claude-ts-to-python-port-worker-9a_direct-ts-to-python-hooks-permissions-substrate-port-from-quarantined-claude-code-ts-release-into-aether-2_6d14a8445f.md

```text
RAW_LEDGER_UPDATE
- actor: Direct Claude-TS-to-Python Port Worker 9A
- task: Direct TS-to-Python hooks + permissions substrate port from quarantined claude-code_ts_release into Aether-2
- event_type: implementation
- summary: Ported the first bounded direct-copy/adaptation slice for hooks and permissions into harness/aether2, integrated it into tool dispatch and loop receipts/traces, added runtime smoke eval artifacts, and documented a publication-gap provenance draft because the quarantined README references an MIT LICENSE file that was not present in the local source snapshot.
- observations: Added canonical hook lifecycle/registry/builtins modules; added a permission manager/rule substrate; threaded permission-request, pre-tool, and post-tool hook execution through native dispatch before side effects; denied actions now return visible typed observations and do not mutate the workspace; receipts and reasoning traces now carry hook and permission metadata; focused and broad Aether pytest suites passed; genericity check passed; codex review helper was blocked by config parse error `unknown variant 'default', expected 'fast' or 'flex' in service_tier`.
- inference: The first direct port slice is viable within Aether's architecture without changing public tool schemas, and the next dependency-ready direct port can move to MCP/runtime tool registry work while carrying forward the license-notice recovery requirement.
- evidence_paths: harness/aether2/hooks/lifecycle.py; harness/aether2/hooks/registry.py; harness/aether2/hooks/builtins.py; harness/aether2/tools/permissions.py; harness/aether2/tools/native.py; harness/aether2/control/loop.py; tests/test_aether2_hooks.py; eval_suite/custom/runtime_policy_hook_smoke/task_pack.json; tracking/collab/public_repo_readiness/claude_ts_direct_port_map.md; tracking/collab/public_repo_readiness/claude_ts_provenance_notice_draft.md
- affected_components: harness.aether2 hooks; harness.aether2 native tool dispatch; harness.aether2 control loop; eval_suite custom smoke packs; public repo readiness provenance docs
- decision_change: Start the direct port program with hooks + permissions as the first live slice and defer MCP/skills/subagents to later slices while preserving explicit provenance and review evidence.
- unresolved_questions: Recover the exact upstream LICENSE/copyright notice before publication; decide whether MCP or skills should be the next direct port slice after tool-registry dependencies are reconciled.
- confidence: high
- commit_message: HOLD - direct TS hooks and permissions port slice remains uncommitted
```
