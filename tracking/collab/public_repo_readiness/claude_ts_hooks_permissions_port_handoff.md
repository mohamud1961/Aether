# Claude TS Hooks + Permissions Port Handoff

- Status: `COMPLETE`
- Originating orchestrator thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Date: `2026-06-15`
- Orchestrator send result: `SENT via codex_app.send_message_to_thread to 019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`

## Objective And Completed Scope

Completed the first bounded direct TS-to-Python port slice requested by the
orchestrator:

- created the exact source-to-target port map for hooks, permissions, MCP,
  skills, and subagents;
- directly ported/adapted the hook lifecycle and permission decision substrate
  into canonical Python modules under `harness/aether2/`;
- integrated pre-tool, permission-request, and post-tool hook handling into the
  Aether native dispatch/loop path without changing public tool schemas;
- added focused tests plus the requested runtime policy hook smoke eval pack;
- documented provenance and the missing-upstream-license publication gap.

## Exact TS Source Files Read

### Ported Now

- `research/sources/codebases/quarantine/claude-code_ts_release/README.md`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/hooks/toolPermission/PermissionContext.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/hooks/toolPermission/handlers/coordinatorHandler.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/hooks/toolPermission/handlers/interactiveHandler.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/hooks/toolPermission/handlers/swarmWorkerHandler.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/hooks/toolPermission/permissionLogging.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/schemas/hooks.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/types/hooks.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/utils/hooks.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/utils/hooks/registerFrontmatterHooks.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/utils/hooks/sessionHooks.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/utils/settings/types.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/types/permissions.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/utils/permissions/PermissionResult.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/utils/permissions/PermissionRule.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/utils/permissions/permissions.ts`

### Inspected For Later Slices

- `research/sources/codebases/quarantine/claude-code_ts_release/src/commands/mcp/index.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/commands/mcp/mcp.tsx`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/commands/skills/index.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/commands/skills/skills.tsx`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/skills/loadSkillsDir.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/skills/bundledSkills.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/loadAgentsDir.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/runAgent.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/commands/agents/index.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/commands/agents/agents.tsx`
- inventory listings for:
  - `src/components/permissions/**`
  - `src/services/mcp/**`
  - `src/components/mcp/**`
  - `src/skills/bundled/**`
  - `src/tools/AgentTool/**`
  - `src/components/agents/**`
  - `src/tasks/*AgentTask/*`

The full classification/result map is persisted in
`tracking/collab/public_repo_readiness/claude_ts_direct_port_map.md`.

## Exact Python And Repo Files Changed

- `harness/aether2/hooks/__init__.py`
- `harness/aether2/hooks/README.md`
- `harness/aether2/hooks/builtins.py`
- `harness/aether2/hooks/lifecycle.py`
- `harness/aether2/hooks/registry.py`
- `harness/aether2/tools/README.md`
- `harness/aether2/tools/__init__.py`
- `harness/aether2/tools/native.py`
- `harness/aether2/tools/permissions.py`
- `harness/aether2/control/loop.py`
- `harness/aether2/__init__.py`
- `tests/test_aether2_hooks.py`
- `eval_suite/custom/runtime_policy_hook_smoke/README.md`
- `eval_suite/custom/runtime_policy_hook_smoke/grader.py`
- `eval_suite/custom/runtime_policy_hook_smoke/task_pack.json`
- `eval_suite/custom/runtime_policy_hook_smoke/fixture/reference/policy_audit.json`
- `eval_suite/custom/runtime_policy_hook_smoke/fixture/workspace/policy_audit.json`
- `eval_suite/boards/runtime_policy_hook_smoke_v1.json`
- `eval_suite/scoreboards/runtime_policy_hook_smoke_v1.example.scoreboard.json`
- `tests/test_runtime_policy_hook_smoke.py`
- `tracking/collab/public_repo_readiness/claude_ts_direct_port_map.md`
- `tracking/collab/public_repo_readiness/claude_ts_provenance_notice_draft.md`

## License / Provenance Findings And Publication Gaps

- The quarantined `README.md` contains an MIT placeholder claim and requires
  inclusion of the original copyright and license notice; that claim is not
  authoritative.
- The expected root `LICENSE`/notice text was not present in the locally
  available quarantined tree during tree inspection.
- A nested history probe did not surface the expected root `LICENSE` artifact
  in the current checkout.
- Result:
  - local port work proceeded;
  - public publication is still blocked on recovering or verifying the exact
    upstream notice text and copyright holder.
- Draft provenance notice persisted:
  - `tracking/collab/public_repo_readiness/claude_ts_provenance_notice_draft.md`

## Feature Behavior Ported

- Permission-request hooks now execute before tool side effects.
- Pre-tool hooks now execute before live tool dispatch on allowed actions.
- Post-tool hooks now execute after live tool dispatch and after permission
  denials.
- Permission decisions now use an explicit allow/deny/ask-style structured
  substrate adapted from the TS source.
- `ask` behavior is intentionally collapsed to a visible denial in this first
  slice because Aether does not yet have the corresponding interactive prompt
  surface.
- Denied actions now return an ordinary typed observation with
  `reason_code=tool_permission_denied`.
- Denied actions do not mutate workspace state.
- Hook/permission metadata now flows into:
  - `ToolInvocationRecord`
  - reasoning trace tool-call summaries
  - host receipt action metadata
- Silent argument rewriting is intentionally blocked in slice 1:
  permission hooks that try to rewrite tool args are denied with an explicit
  message instead of mutating inputs invisibly.

## Validation And Test Results

- `python3 -m py_compile harness/aether2/hooks/__init__.py harness/aether2/hooks/lifecycle.py harness/aether2/hooks/registry.py harness/aether2/hooks/builtins.py harness/aether2/tools/permissions.py harness/aether2/tools/native.py harness/aether2/tools/__init__.py harness/aether2/control/loop.py harness/aether2/__init__.py eval_suite/custom/runtime_policy_hook_smoke/grader.py tests/test_aether2_hooks.py tests/test_runtime_policy_hook_smoke.py`
  - Result: passed
- `python3 -m pytest tests/test_aether2_hooks.py tests/test_runtime_policy_hook_smoke.py tests/test_aether2_tools.py tests/test_aether2_loop.py tests/test_aether2_receipts.py tests/test_aether2_executor.py tests/test_aether2_runtime_identity.py tests/test_public_manifest_repair_smoke.py -q -p no:cacheprovider`
  - Result: `80 passed in 59.42s`
- `python3 tools/aether2_genericity_check.py`
  - Result: passed
- `git diff --check -- harness/aether2 tests eval_suite tracking/collab/public_repo_readiness`
  - Result: passed
- broad Aether baseline because loop/tool dispatch changed:
  - `python3 -m pytest tests/test_aether2_*.py tests/test_run_aether2_g2.py tests/test_run_aether2_g3_official.py tests/test_run_aether2_tournament.py -q -p no:cacheprovider`
  - Result: `245 passed in 72.12s`

## Review Findings And Dispositions

- Codex review helper status:
  - blocked
  - exact error preserved:
    - `Error loading config.toml: unknown variant 'default', expected 'fast' or 'flex' in service_tier`
- Manual adversarial review scope covered:
  - port fidelity to the TS permission/hook lifecycle;
  - license/provenance handling;
  - hidden control-plane behavior;
  - denial visibility;
  - side-effect prevention;
  - schema drift;
  - genericity.
- Manual review disposition:
  - accepted findings: none
  - rejected/non-bug concerns:
    - no interactive `ask` flow yet: intentional and explicitly documented as
      a bounded first-slice adaptation, not a silent behavior mismatch
    - no permission persistence/settings writer yet: intentionally deferred to
      later slices

## Persisted RAW_LEDGER_UPDATE

- Recorder output:
  - `tracking/ledger/inbox/2026-06-15/201514_direct-claude-ts-to-python-port-worker-9a_direct-ts-to-python-hooks-permissions-substrate-port-from-quarantined-claude-code-ts-release-into-aether-2_6d14a8445f.md`

## Exact Next Dependency-Ready Direct Port Slice

- Recommended next slice: `MCP`
- Reason:
  - hooks + permissions substrate now exists;
  - MCP is the next clean runtime/tool-registry boundary before skill loading
    and subagent orchestration;
  - skills and agents both depend on a stable tool registry surface, which MCP
    work can establish without needing the full UI layer.

## External State Confirmation

- No branch/worktree/commit/push was created.
- No eval/full task run was started.
- No VM/container lifecycle action was started.
- No credential, auth, or network-dependent proprietary surface was touched.
- No background process, server, or external job was intentionally left running.
