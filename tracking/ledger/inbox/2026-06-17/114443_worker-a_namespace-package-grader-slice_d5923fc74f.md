# Raw Ledger Update

- recorded_at_utc: 2026-06-17T11:44:43.551828+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Worker A
- task: namespace/package/grader slice
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: d5923fc74fcf2490d59706a5ea47aea5ee27f1909f8b95531bf632da1d6dc5ef
- commit_message: Add bundle-based MCP smoke and ship aether packages
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-17/114443_worker-a_namespace-package-grader-slice_d5923fc74f.md

```text
RAW_LEDGER_UPDATE
- actor: Worker A
- task: namespace/package/grader slice
- event_type: implementation
- summary: Fixed packaging discovery so the public aether tree ships, redirected the MCP smoke test to the canonical family pack, and hardened the MCP smoke grader around a paired audit/trace bundle instead of a single JSON blob.
- observations: The public smoke test previously pointed at eval_suite/custom/mcp_registry_contract_smoke even though the checked-in pack lives under eval_suite/families/tooling/mcp_registry_contract_smoke. The grader now requires mcp_registry_trace.json alongside mcp_audit.json and compares the trace projection against the audit summary. Editable install succeeded in a clean venv after adding aether* to setuptools package discovery.
- inference: The canonical harness namespace is shippable only if the aether package tree is included in the distribution; the extra trace artifact makes direct JSON copying insufficient for the smoke.
- evidence_paths: ["/Users/mohamud/Downloads/harnesseng/pyproject.toml", "/Users/mohamud/Downloads/harnesseng/harness/aether2/__init__.py", "/Users/mohamud/Downloads/harnesseng/eval_suite/families/tooling/mcp_registry_contract_smoke/grader.py", "/Users/mohamud/Downloads/harnesseng/eval_suite/families/tooling/mcp_registry_contract_smoke/task_pack.json", "/Users/mohamud/Downloads/harnesseng/eval_suite/families/tooling/mcp_registry_contract_smoke/fixture/reference/mcp_audit.json", "/Users/mohamud/Downloads/harnesseng/eval_suite/families/tooling/mcp_registry_contract_smoke/fixture/workspace/mcp_audit.json", "/Users/mohamud/Downloads/harnesseng/eval_suite/families/tooling/mcp_registry_contract_smoke/fixture/reference/mcp_registry_trace.json", "/Users/mohamud/Downloads/harnesseng/eval_suite/families/tooling/mcp_registry_contract_smoke/fixture/workspace/mcp_registry_trace.json", "/Users/mohamud/Downloads/harnesseng/tests/test_mcp_registry_contract_smoke.py"]
- affected_components: packaging, public namespace shim, eval substrate smoke pack, grader hardening
- decision_change: Keep the MCP public smoke as a paired artifact contract and ship the aether package tree with the public harness namespace.
- unresolved_questions: None for this slice; broader benchmark substrate changes remain out of scope.
- confidence: high
- commit_message: Add bundle-based MCP smoke and ship aether packages
```
