# Claude TS Subagent Loader/Handoff Port Handoff

- Status: `COMPLETE`
- Originating orchestrator thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Date: `2026-06-15`
- Orchestrator send target: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Orchestrator send result: `SENT via codex_app.send_message_to_thread to 019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`

## Objective And Completed Scope

Completed the bounded direct TS-to-Python subagent slice requested by the
orchestrator:

- ported/adapted the Claude TS AgentTool agent-definition loader into
  canonical Python modules under `harness/aether2/agents/`;
- added bounded worker task packets and structured worker handoffs with
  explicit ownership, evidence, unresolved-risk, and external-state fields;
- added a deterministic local/fake runtime boundary that resolves skill refs,
  MCP refs, and allowed-tool refs visibly without spawning actual Codex
  threads, background swarms, or remote agents;
- updated the direct port map with exact source coverage, exclusions, and
  simplifications;
- added focused tests plus the requested deterministic
  `subagent_handoff_contract_smoke` eval pack, board, and example scoreboard.

## Requirement-By-Requirement Disposition

- `loader.py` for filesystem agent definition loading/frontmatter parsing
  - complete
- `task.py` for bounded worker task packet and ownership/scope fields
  - complete
- `handoff.py` for structured worker handoff/result evidence
  - complete
- explicit local/fake runtime boundary with no real thread spawning
  - complete
- skill refs and MCP refs retained/resolved or failed visibly
  - complete
- required eval smoke pack, board, scoreboard, and focused tests
  - complete
- public exports in `harness/aether2/agents/__init__.py` and
  `harness/aether2/__init__.py`
  - complete

## Exact TS Source Files Read

### Ported Now

- `research/sources/codebases/quarantine/claude-code_ts_release/README.md`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/loadAgentsDir.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/runAgent.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/AgentTool.tsx`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/agentToolUtils.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/prompt.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/tasks/LocalAgentTask/LocalAgentTask.tsx`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/tasks/InProcessTeammateTask/InProcessTeammateTask.tsx`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/tasks/InProcessTeammateTask/types.ts`

### Inspected And Explicitly Excluded Or Deferred

- inventory-only / bounded context:
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/builtInAgents.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/constants.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/agentMemory.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/agentMemorySnapshot.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/forkSubagent.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/resumeAgent.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/commands/agents/index.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/commands/agents/agents.tsx`
- excluded UI-only surfaces:
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/UI.tsx`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/agentDisplay.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/agentColorManager.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/components/agents/**`
- excluded bundled prompt/content surfaces:
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/built-in/**`
- excluded remote/proprietary runtime:
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/tasks/RemoteAgentTask/RemoteAgentTask.tsx`

## Exact Python, Eval, Test, And Doc Files Changed

- `harness/aether2/agents/README.md`
- `harness/aether2/agents/__init__.py`
- `harness/aether2/agents/loader.py`
- `harness/aether2/agents/task.py`
- `harness/aether2/agents/handoff.py`
- `harness/aether2/agents/runtime.py`
- `harness/aether2/tools/registry.py`
- `harness/aether2/skills/loader.py`
- `harness/aether2/__init__.py`
- `tests/test_aether2_agents.py`
- `tests/test_subagent_handoff_contract_smoke.py`
- `eval_suite/custom/subagent_handoff_contract_smoke/README.md`
- `eval_suite/custom/subagent_handoff_contract_smoke/grader.py`
- `eval_suite/custom/subagent_handoff_contract_smoke/task_pack.json`
- `eval_suite/custom/subagent_handoff_contract_smoke/fixture/reference/subagent_audit.json`
- `eval_suite/custom/subagent_handoff_contract_smoke/fixture/workspace/subagent_audit.json`
- `eval_suite/boards/subagent_handoff_contract_smoke_v1.json`
- `eval_suite/scoreboards/subagent_handoff_contract_smoke_v1.example.scoreboard.json`
- `tracking/collab/public_repo_readiness/claude_ts_direct_port_map.md`
- `tracking/collab/public_repo_readiness/claude_ts_subagent_port_handoff.md`

## Behavior Ported

- Deterministic markdown agent loading from a bounded agents directory.
- Frontmatter parsing/retention for:
  - tool allowlists
  - disallowed tools
  - skill refs
  - MCP server refs / inline MCP configs
  - required MCP server patterns
  - permission mode
  - hooks metadata
  - max turns
  - initial prompt
  - background flag
  - memory/isolation metadata
- Active-agent precedence and MCP requirement filtering aligned with the TS
  source’s registry concepts.
- Explicit worker task packet creation carrying objective, prompt, scope,
  out-of-scope, files to touch, exit criteria, evidence expectations,
  ownership, and no-background defaults.
- Structured handoff carrying status, summary, completed scope, requirement
  disposition, files changed, evidence paths, validation commands, unresolved
  risks, blockers, review dispositions, recommended next action, and external
  state.
- Explicit local/fake runtime preparation that resolves:
  - selected skill refs via the already-ported skill registry
  - MCP server refs via the already-ported tool registry
  - allowed tool refs via the already-ported tool registry
  - parent-visible runtime issues for missing/unresolved refs
- No silent background execution assumption:
  background requests are surfaced as visible runtime issues instead of
  launching hidden work.

## Simplifications And Deferred Pieces

- No real model query loop, transcript persistence, or prompt-cache plumbing.
- No actual Codex thread spawning, teammate mailbox runtime, or remote agent
  session flow.
- No built-in Claude TS bundled agent prompt content was ported.
- No live agent-specific MCP server startup/cleanup was ported; inline configs
  are retained and surfaced but not activated in this local/fake slice.
- No frontmatter hook execution/registration was ported here; hook metadata is
  retained only.
- No worktree/remote isolation implementation was ported; those values are
  metadata only in this slice.
- No UI menus, React/Ink rendering, auth/provider routing, telemetry,
  analytics, or Claude branding were ported.

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

- `python3 -m py_compile harness/aether2/skills/loader.py harness/aether2/agents/__init__.py harness/aether2/agents/loader.py harness/aether2/agents/task.py harness/aether2/agents/handoff.py harness/aether2/agents/runtime.py harness/aether2/tools/registry.py harness/aether2/__init__.py tests/test_aether2_agents.py tests/test_subagent_handoff_contract_smoke.py tests/test_aether2_skills.py tests/test_skill_loader_contract_smoke.py eval_suite/custom/subagent_handoff_contract_smoke/grader.py`
  - Result: passed
- `python3 -m pytest tests/test_aether2_agents.py tests/test_subagent_handoff_contract_smoke.py tests/test_aether2_skills.py tests/test_skill_loader_contract_smoke.py tests/test_aether2_mcp_registry.py tests/test_mcp_registry_contract_smoke.py tests/test_aether2_hooks.py tests/test_runtime_policy_hook_smoke.py tests/test_public_manifest_repair_smoke.py -q -p no:cacheprovider`
  - Result: `43 passed in 4.64s`
- `python3 tools/aether2_genericity_check.py`
  - Result: passed
- `git diff --check -- harness/aether2 tests eval_suite tracking/collab/public_repo_readiness`
  - Result: passed
- broad Aether baseline:
  - Not run
  - Reason: no loop execution semantics, model prompt flow, or dispatch
    behavior were changed; the only shared-runtime edits were additive
    `ToolRegistry` introspection helpers and a shared frontmatter parser fix,
    both covered by the focused skills/MCP/hooks smoke and unit suites above.

## Review Findings And Dispositions

- Codex review helper status:
  - blocked
  - exact helper run:
    - `~/.codex/skills/codex-review/scripts/codex-review`
  - exact error preserved:
    - `review command: codex review --uncommitted`
    - `WARNING: proceeding, even though we could not update PATH: Operation not permitted (os error 1)`
    - `Error loading config.toml: unknown variant 'default', expected 'fast' or 'flex' in service_tier`
- Manual adversarial review scope covered:
  - direct-port fidelity for agent markdown loading/frontmatter parsing;
  - worker-boundary truthfulness and handoff completeness;
  - hidden background execution risk;
  - visible unresolved-risk propagation to the parent;
  - skill/MCP reference safety and explicit failure surfacing;
  - genericity and public-notice boundaries.
- Manual review disposition:
  - accepted findings:
    - the shared frontmatter parser initially rejected inline list-item mapping
      YAML used by agent `mcpServers`; fixed in `harness/aether2/skills/loader.py`
      and reran focused + regression coverage
  - remaining actionable findings:
    - none

## Persisted RAW_LEDGER_UPDATE

- Recorder output:
  - `tracking/ledger/inbox/2026-06-15/220606_direct-claude-ts-to-python-port-worker-12_port-adapt-the-claude-ts-agenttool-subagent-loader-and-structured-handoff-boundary-into-harnesseng-python_d6561982c7.md`

## Exact Next Dependency-Ready Step

- Direct-port dependency chain status:
  - ready to move to AI-native engineering showcase work
- Reason:
  - hooks/permissions, MCP, skills, and the explicit local/fake subagent
    loader/task/handoff/runtime boundary now exist as reusable public substrate;
  - remaining quarantined TS surfaces are primarily UI-only, remote/auth,
    telemetry, or bundled prompt content rather than dependency-critical public
    runtime substrate.

## External State Confirmation

- No branch/worktree/commit/push was created.
- No eval/full task run was started.
- No VM/container lifecycle action was started.
- No credential, auth, or live network-dependent proprietary surface was
  touched.
- No Codex thread, teammate, background worker, server, or external job
  remains intentionally active from this worker’s implementation.
