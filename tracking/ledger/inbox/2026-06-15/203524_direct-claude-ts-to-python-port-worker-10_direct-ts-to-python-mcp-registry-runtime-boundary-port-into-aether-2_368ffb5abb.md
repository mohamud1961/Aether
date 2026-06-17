# Raw Ledger Update

- recorded_at_utc: 2026-06-15T20:35:24.715202+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Direct Claude-TS-to-Python Port Worker 10
- task: Direct TS-to-Python MCP registry/runtime boundary port into Aether-2
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 368ffb5abbd8432cac4c1c55474d9dcb9c5c2d59cb9f760a183d968d100b0ec9
- commit_message: HOLD - delegated worker slice completed without branch/commit by instruction
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-15/203524_direct-claude-ts-to-python-port-worker-10_direct-ts-to-python-mcp-registry-runtime-boundary-port-into-aether-2_368ffb5abb.md

```text
RAW_LEDGER_UPDATE
- actor: Direct Claude-TS-to-Python Port Worker 10
- task: Direct TS-to-Python MCP registry/runtime boundary port into Aether-2
- event_type: implementation
- summary: Ported a bounded MCP registry/runtime surface from quarantined Claude TS sources into Aether-2 Python, integrated it with the shared hook/permission dispatch path, and added a deterministic MCP registry contract smoke eval.
- observations: Added canonical Python MCP config/state/schema-mapping and fake-local server modules under harness/aether2/tools; introduced a native+MCP tool registry consumed by the loop; MCP success/timeout/error/unavailable/schema-mapping failures now surface as typed observations; added focused runtime tests plus eval_suite/custom/mcp_registry_contract_smoke with board and example scoreboard; broad Aether baseline remained green after the loop/tool advertisement change.
- inference: The hooks+permissions substrate was sufficient for the next dependency-ready direct port slice; MCP can now act as a stable registry/runtime boundary for later skills-loader work without introducing UI/auth/provider dependencies.
- evidence_paths: harness/aether2/tools/mcp.py; harness/aether2/tools/registry.py; harness/aether2/control/loop.py; tests/test_aether2_mcp_registry.py; tests/test_mcp_registry_contract_smoke.py; eval_suite/custom/mcp_registry_contract_smoke/; tracking/collab/public_repo_readiness/claude_ts_direct_port_map.md; tracking/collab/public_repo_readiness/claude_ts_mcp_port_handoff.md
- affected_components: harness/aether2/tools; harness/aether2/control; eval_suite/custom; tracking/collab/public_repo_readiness
- decision_change: Move the next direct TS-to-Python dependency slice from MCP to skills loader/registry, since the MCP registry/runtime boundary is now in place.
- unresolved_questions: Recover or verify the upstream MIT notice text before any public publication; decide how much of TS failed/disabled connection management should be ported before live remote transports are admitted.
- confidence: medium-high
- commit_message: HOLD - delegated worker slice completed without branch/commit by instruction
```
