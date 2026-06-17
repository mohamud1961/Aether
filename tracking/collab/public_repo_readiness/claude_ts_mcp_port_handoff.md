# Claude TS MCP Registry/Runtime Port Handoff

- Status: `COMPLETE`
- Originating orchestrator thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Date: `2026-06-15`
- Orchestrator send target: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Orchestrator send result: `SENT via codex_app.send_message_to_thread to 019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`

## Objective And Completed Scope

Completed the bounded direct TS-to-Python MCP slice requested by the
orchestrator:

- ported/adapted the Claude TS MCP tool-registry/runtime boundary into
  canonical Python modules under `harness/aether2/tools/`;
- kept UI/auth/provider/telemetry/marketplace surfaces excluded;
- integrated the new registry narrowly into the existing Aether loop so native
  tools and MCP tools share one typed invocation/observation path;
- reused the previously ported hooks/permissions substrate so MCP invocations
  are permission-checkable and hook-observable;
- added focused tests plus the requested deterministic
  `mcp_registry_contract_smoke` eval pack, board, and example scoreboard;
- updated the direct port map with exact MCP source coverage, exclusions, and
  simplifications.

## Exact TS Source Files Read

### Ported Now

- `research/sources/codebases/quarantine/claude-code_ts_release/README.md`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/commands/mcp/index.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/commands/mcp/mcp.tsx`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/commands/mcp/addCommand.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/services/mcp/types.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/services/mcp/config.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/services/mcp/client.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/services/mcp/MCPConnectionManager.tsx`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/services/mcp/mcpStringUtils.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/services/mcp/normalization.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/Tool.ts`

### Inspected And Explicitly Excluded Or Deferred

- UI-only / command presentation:
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/components/mcp/**`
  - React/Ink portions of `src/commands/mcp/mcp.tsx`
- auth / provider / proprietary / telemetry surfaces:
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/commands/mcp/xaaIdpCommand.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/services/mcp/auth.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/services/mcp/claudeai.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/services/mcp/headersHelper.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/services/mcp/channelPermissions.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/services/mcp/useManageMCPConnections.ts`
- future integration surfaces:
  - MCP resources/prompts/skills bridge from `src/services/mcp/client.ts`
  - persistent config/policy/enterprise handling from `src/services/mcp/config.ts`

## Exact Python, Eval, Test, And Doc Files Changed

- `harness/aether2/tools/mcp.py`
- `harness/aether2/tools/registry.py`
- `harness/aether2/tools/native.py`
- `harness/aether2/tools/__init__.py`
- `harness/aether2/control/loop.py`
- `harness/aether2/__init__.py`
- `tests/test_aether2_mcp_registry.py`
- `tests/test_mcp_registry_contract_smoke.py`
- `eval_suite/custom/mcp_registry_contract_smoke/README.md`
- `eval_suite/custom/mcp_registry_contract_smoke/grader.py`
- `eval_suite/custom/mcp_registry_contract_smoke/task_pack.json`
- `eval_suite/custom/mcp_registry_contract_smoke/fixture/reference/mcp_audit.json`
- `eval_suite/custom/mcp_registry_contract_smoke/fixture/workspace/mcp_audit.json`
- `eval_suite/boards/mcp_registry_contract_smoke_v1.json`
- `eval_suite/scoreboards/mcp_registry_contract_smoke_v1.example.scoreboard.json`
- `tracking/collab/public_repo_readiness/claude_ts_direct_port_map.md`
- `tracking/collab/public_repo_readiness/claude_ts_mcp_port_handoff.md`

## Behavior Ported

- MCP server config/state abstraction now exists in Python with bounded TS-like
  connection states: `connected`, `failed`, `needs-auth`, `pending`,
  `disabled`.
- TS MCP naming behavior is ported into Python:
  - ASCII-only normalization;
  - special `claude.ai ` underscore-collapse rule;
  - fully-qualified `mcp__server__tool` tool names.
- Native and MCP tools now share one registry/invocation boundary via
  `harness/aether2/tools/registry.py`.
- The loop can advertise registry-provided schemas without changing the native
  public `TOOL_NAMES`/`TOOL_SCHEMAS` constants.
- Permission-request, pre-tool, and post-tool hooks now also cover MCP tool
  invocations.
- MCP success, timeout, unavailable, schema-mapping failure, and tool-error
  outcomes surface as ordinary typed observations/envelopes instead of hidden
  exceptions.
- A deterministic fake/local MCP server fixture exists for tests and eval smoke
  work; no live network/server dependency is required.

## Simplifications And Deferred Pieces

- No real SDK/network MCP client was ported in this slice.
- No auth/OAuth/XAA/provider flows were ported.
- No UI/Ink/React MCP management surface was ported.
- No persistent MCP config writers, enterprise policy merges, or marketplace
  registry handling were ported.
- No resources/prompts/skills discovery bridge was ported.
- No background reconnect loop or app-state React context was ported.
- Failed/disabled connection registration is kept as a bounded local test/runtime
  surface only; there is no full TS-style live connection manager yet.

## License / Provenance Status

- The quarantined `README.md` contains an MIT placeholder claim and requires
  inclusion of the original copyright and license notice; that claim is not
  authoritative.
- The local quarantined tree still does not surface the expected root
  `LICENSE`/notice text.
- Result:
  - local port/adaptation work proceeded;
  - public publication remains blocked on recovering/verifying the exact
    upstream notice text and copyright holder.
- Existing provenance draft still applies:
  - `tracking/collab/public_repo_readiness/claude_ts_provenance_notice_draft.md`

## Validation Commands And Results

- `python3 -m pytest tests/test_aether2_mcp_registry.py tests/test_mcp_registry_contract_smoke.py -q -p no:cacheprovider`
  - Result: `10 passed in 2.46s`
- `python3 -m pytest tests/test_aether2_mcp_registry.py tests/test_mcp_registry_contract_smoke.py tests/test_aether2_hooks.py tests/test_aether2_tools.py tests/test_aether2_loop.py tests/test_aether2_executor.py tests/test_aether2_receipts.py tests/test_aether2_runtime_identity.py tests/test_runtime_policy_hook_smoke.py tests/test_public_manifest_repair_smoke.py -q -p no:cacheprovider`
  - Result: `89 passed in 56.63s`
- broad Aether baseline because loop/tool advertisement changed:
  - `python3 -m pytest tests/test_aether2_*.py tests/test_run_aether2_g2.py tests/test_run_aether2_g3_official.py tests/test_run_aether2_tournament.py -q -p no:cacheprovider`
  - Result: `250 passed in 70.11s (0:01:10)`
- `python3 -m py_compile harness/aether2/control/loop.py harness/aether2/tools/native.py harness/aether2/tools/mcp.py harness/aether2/tools/registry.py harness/aether2/tools/__init__.py harness/aether2/__init__.py tests/test_aether2_mcp_registry.py tests/test_mcp_registry_contract_smoke.py eval_suite/custom/mcp_registry_contract_smoke/grader.py`
  - Result: passed
- `python3 tools/aether2_genericity_check.py`
  - Result: passed
- `git diff --check -- harness/aether2 tests eval_suite tracking/collab/public_repo_readiness`
  - Result: passed

## Review Findings And Dispositions

- Codex review helper status:
  - blocked
  - exact error preserved:
    - `Error loading config.toml: unknown variant 'default', expected 'fast' or 'flex' in service_tier`
- Manual adversarial review scope covered:
  - direct-port fidelity for MCP naming/config/state/schema mapping;
  - hook/permission integration on MCP calls;
  - visible timeout/error/unavailable semantics;
  - hidden exception/network dependency risks;
  - genericity and eval contamination boundaries;
  - provenance/public notice gaps.
- Manual review disposition:
  - accepted findings:
    - MCP normalization originally used Python `isalnum()`, which would admit
      non-ASCII characters unlike the TS regex contract; fixed to ASCII-only
      normalization and added a focused regression test.
  - rejected / bounded-by-scope concerns:
    - no live remote SDK transport yet: intentional slice bound, covered by the
      fake/local server contract requirement
    - no MCP resources/prompts/auth flows yet: intentionally deferred to later
      slices, not silent omissions inside this slice

## Exact Next Dependency-Ready Direct-Port Slice

- Recommended next slice: `skills loader/registry`
- Reason:
  - hooks/permissions and the MCP registry/runtime boundary now exist;
  - skills can consume the new registry without requiring UI/auth/provider
    surfaces;
  - subagent runtime still depends on both skills and MCP stabilization.

## Persisted RAW_LEDGER_UPDATE

- Recorder output:
  - `tracking/ledger/inbox/2026-06-15/203524_direct-claude-ts-to-python-port-worker-10_direct-ts-to-python-mcp-registry-runtime-boundary-port-into-aether-2_368ffb5abb.md`

## External State Confirmation

- No branch/worktree/commit/push was created.
- No eval/full task run was started.
- No VM/container lifecycle action was started.
- No credential, auth, or live network-dependent proprietary surface was
  touched.
- No background process, server, or external job remains intentionally active.
