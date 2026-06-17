# Claude TS Direct Port Map

Date: `2026-06-15`

## Scope

This map records the direct TS-to-Python port inventory for the quarantined
`research/sources/codebases/quarantine/claude-code_ts_release/` surfaces
requested for public-repo readiness work.

The first bounded implementation slice covered hooks and permissions. The
second bounded implementation slice added the MCP registry/runtime boundary on
top of that substrate. The third bounded implementation slice ported the
skills loader/registry/model-visible rendering surface. The current bounded
implementation slice ports the explicit subagent loader/task/handoff/runtime
boundary as a deterministic local/fake worker surface.

## License And Provenance Inspection

- `README.md` was read first and contains an MIT placeholder claim that
  requires inclusion of the original copyright and license notice in copies;
  that claim is not authoritative.
- A root `LICENSE`/`LICENSE.md`/`NOTICE` file was not found in the quarantined
  working tree during local tree inspection.
- A nested git-history probe for `LICENSE*` paths did not surface the expected
  root license artifact in the currently available checkout.
- Publication status: implementation work may continue locally, but public
  publication still needs the upstream notice text recovered or verified.

## Hooks And Permissions

| TS source | Classification | Python target | Port status | Exact behavior copied/adapted | Simplified or deferred dependencies |
| --- | --- | --- | --- | --- | --- |
| `README.md` | provenance | docs + handoff + provenance draft | ported now | MIT placeholder claim and notice requirement captured in local docs/handoff | Missing upstream `LICENSE` text remains unresolved |
| `src/hooks/toolPermission/PermissionContext.ts` | hooks + permissions core | `harness/aether2/hooks/lifecycle.py`, `harness/aether2/tools/permissions.py` | ported now | copied the allow/deny/ask decision shape, permission-request hook execution concept, hook-first permission flow, and audited decision metadata | no interactive queue, no classifier, no permission persistence, no argument mutation support in slice 1 |
| `src/hooks/toolPermission/handlers/coordinatorHandler.ts` | permissions control flow | `harness/aether2/tools/permissions.py`, `harness/aether2/tools/native.py` | ported now | copied the sequential flow of permission hooks before falling through to other permission logic | no classifier stage yet |
| `src/hooks/toolPermission/handlers/interactiveHandler.ts` | permissions UX/runtime boundary | `harness/aether2/tools/native.py` | ported now (adapted) | copied the idea that permission denial becomes a normal surfaced result and that post-decision handling still runs | interactive user prompt, bridge callbacks, channel callbacks, classifier races, and queue state deferred |
| `src/hooks/toolPermission/handlers/swarmWorkerHandler.ts` | subagent permission boundary | `harness/aether2/agents/runtime.py`, `harness/aether2/agents/handoff.py` | ported now (bounded adaptation) | copied the requirement that worker permission/handoff outcomes stay explicit and visible to the parent rather than silently mutating or backgrounding | mailbox, swarm poller, callback registry, and interactive teammate surfaces remain deferred |
| `src/hooks/toolPermission/permissionLogging.ts` | telemetry/audit | `harness/aether2/control/loop.py`, receipts/trace metadata | ported now (adapted) | copied the central idea that permission outcomes should be explicitly logged/audited | analytics, OTel counters, code-edit telemetry excluded |
| `src/commands/hooks/index.ts` | UI-only command entry | none | excluded | inventory only; command shell around hook config UI | local JSX command system excluded |
| `src/commands/hooks/hooks.tsx` | UI-only command entry | none | excluded | inventory only; view wrapper for hook config menu | React/Ink UI excluded |
| `src/commands/permissions/index.ts` | UI-only command entry | none | excluded | inventory only; command alias surface for permission UI | local JSX command system excluded |
| `src/commands/permissions/permissions.tsx` | UI-only command entry | none | excluded | inventory only; wrapper around permission rule UI | React/Ink UI excluded |
| `src/components/permissions/**` | UI-only | none | excluded | inventory-inspected as interactive permission/config UI, not runtime core | dialogs, review UX, diff UX, retry UX, rules editing UI deferred/excluded |
| `src/schemas/hooks.ts` | hook schema support | `harness/aether2/hooks/registry.py`, `harness/aether2/hooks/lifecycle.py` | ported now (adapted) | copied matcher-array mental model and hook command/event separation into a Python registry | command/prompt/http/agent hook kinds not implemented yet; first slice uses function callbacks only |
| `src/types/hooks.ts` | hook event/result contract | `harness/aether2/hooks/lifecycle.py` | ported now (adapted) | copied `PermissionRequest`, `PreToolUse`, `PostToolUse` event/result concepts and structured hook outputs | async hooks, prompt requests, MCP output rewrite hooks, user-prompt/session hooks deferred |
| `src/utils/hooks.ts` | lifecycle execution engine | `harness/aether2/hooks/registry.py`, `harness/aether2/tools/native.py` | ported now (adapted) | copied session hook execution around lifecycle events and explicit hook result handling | shell hooks, prompt hooks, HTTP hooks, agent hooks, plugin hooks, session env files, telemetry, async background hooks deferred |
| `src/utils/hooks/registerFrontmatterHooks.ts` | hook registration support | `harness/aether2/hooks/registry.py` | later | inspected for future skill/agent-scoped hook registration | frontmatter ingestion deferred to skills/subagents slices |
| `src/utils/hooks/sessionHooks.ts` | hook registry core | `harness/aether2/hooks/registry.py` | ported now (adapted) | copied session-scoped matcher registry and callback registration concepts | app-state mutation, removal APIs, once/timeout semantics mostly deferred |
| `src/utils/settings/types.ts` | settings schema support | `harness/aether2/tools/permissions.py`, future skill/agent loaders | later | inspected for future hook/permissions/skills/agents config boundaries | full settings schema, marketplace, MCP allowlists, plugin-only policy deferred |
| `src/utils/permissions/PermissionResult.ts` | permissions types | `harness/aether2/hooks/lifecycle.py` | ported now (adapted) | copied decision terminology and behavior descriptions into Python decision types | none |
| `src/types/permissions.ts` | permissions types | `harness/aether2/hooks/lifecycle.py`, `harness/aether2/tools/permissions.py` | ported now (adapted) | copied behavior union, rule/update/decision vocabulary, and mode awareness where relevant | persistence destinations, content blocks, classifier state, and full mode machine deferred |
| `src/utils/permissions/PermissionRule.ts` | permissions rules | `harness/aether2/tools/permissions.py` | ported now (adapted) | copied tool-name plus optional content matcher concept | complex tool-specific parsers deferred |
| `src/utils/permissions/permissions.ts` | permissions evaluator | `harness/aether2/tools/permissions.py`, `harness/aether2/tools/native.py` | ported now (bounded) | copied the idea that permission evaluation returns structured decisions before tool side effects | interactive ask flow, auto mode, classifier, safe-tool allowlist, tool-specific permission logic deferred |

## MCP

| TS source | Classification | Python target | Port status | Exact behavior copied/adapted | Simplified or deferred dependencies |
| --- | --- | --- | --- | --- | --- |
| `src/commands/mcp/index.ts` | MCP command entry | `tracking/collab/public_repo_readiness/claude_ts_direct_port_map.md`, handoff docs | inspected now | copied command-surface intent only to classify enable/disable/reconnect as management/UI, not runtime core | JSX/command UI deferred |
| `src/commands/mcp/mcp.tsx` | MCP command + UI bridge | docs only; no runtime port target | inspected now | copied the enable/disable/reconnect state vocabulary so Python connection state names remain aligned | React/Ink UI and plugin redirect excluded |
| `src/commands/mcp/addCommand.ts` | MCP config command support | `harness/aether2/tools/mcp.py` | ported now (adapted) | copied bounded config validation ideas: typed transport/config shape, reserved management/auth separation, and explicit local-vs-remote distinction | persistent config writers, headers/env parsing, OAuth secret storage, analytics, and CLI UX deferred |
| `src/commands/mcp/xaaIdpCommand.ts` | provider/auth/telemetry | none | excluded | inventory-inspected as auth flow | auth/OAuth/proprietary surfaces excluded |
| `src/services/mcp/types.ts` | MCP types | `harness/aether2/tools/mcp.py` | ported now (adapted) | copied scoped config vocabulary, connection-state union (`connected/failed/needs-auth/pending/disabled`), and serialized-tool naming concepts | remote-only config variants (`ws`, `claudeai-proxy`, IDE-specific types) recorded but not implemented in runtime slice |
| `src/services/mcp/config.ts` | MCP config | `harness/aether2/tools/mcp.py` | ported now (bounded) | copied typed config records, disabled/failed state semantics, and direct config-vs-runtime separation | config file discovery, policy allowlists, dedup across scopes/plugins/connectors, enterprise policy, and persistent enable/disable settings deferred |
| `src/services/mcp/MCPConnectionManager.tsx` | MCP connection-state authority | `harness/aether2/tools/mcp.py` | ported now (adapted) | copied explicit connection state naming and reconnect-attempt fields into Python connection records without React context coupling | React hooks/context, app-state mutation, UI callbacks, and background reconnection loops deferred |
| `src/services/mcp/client.ts` | MCP discovery/invocation runtime | `harness/aether2/tools/mcp.py`, `harness/aether2/tools/registry.py`, `harness/aether2/control/loop.py` | ported now (bounded) | copied MCP name normalization, fully-qualified `mcp__server__tool` naming, deterministic tool discovery via connected clients, raw input-schema passthrough into function-call schemas, typed visible timeout/error/unavailable handling, and connection/tool separation from native tools | no real SDK client, no network transport, no OAuth/auth refresh, no resources/prompts/skills discovery, no large-output persistence, no progress streaming, no session cache, no claude.ai/proxy/IDE hooks |
| `src/services/mcp/mcpStringUtils.ts` | MCP naming utilities | `harness/aether2/tools/mcp.py` | ported now | copied server/tool normalization and fully-qualified tool-name builder semantics | display-name helpers and permission helper bridge beyond naming deferred |
| `src/services/mcp/normalization.ts` | MCP naming normalization | `harness/aether2/tools/mcp.py` | ported now | copied ASCII-only normalization and the special `claude.ai ` underscore-collapse rule | none |
| `src/Tool.ts` (`Tool`, `toolMatchesName`, MCP-facing fields) | generic tool contract context | `harness/aether2/tools/registry.py`, `harness/aether2/tools/mcp.py` | ported now (adapted) | copied the idea that MCP tools live beside native tools with explicit `isMcp`-style identity, stable names, and shared invocation surface | React/provider/UI progress plumbing deferred |
| `src/services/mcp/*.ts*` (remaining) | MCP support + auth + UI coupling | later mixed MCP slices | deferred/excluded | inventory-inspected to separate runtime pieces from auth/UI/registry extras | `auth.ts`, `headersHelper.ts`, `channelPermissions.ts`, `claudeai.ts`, OAuth, registry marketplace, notifications, VS Code helpers, and provider-specific flows deferred or excluded |
| `src/components/mcp/**` | UI-only | none | excluded | inventory-inspected as settings/list/detail dialogs | React/Ink UI excluded |

## Skills

| TS source | Classification | Python target | Port status | Exact behavior copied/adapted | Simplified or deferred dependencies |
| --- | --- | --- | --- | --- | --- |
| `src/commands/skills/index.ts` | skill command entry | future `harness/aether2/skills/registry.py` | later | inspected as user command surface | JSX UI deferred |
| `src/commands/skills/skills.tsx` | UI-only | none | excluded | inventory-inspected wrapper around skill menu | React/Ink UI excluded |
| `src/skills/loadSkillsDir.ts` | skills runtime core | `harness/aether2/skills/loader.py`, `harness/aether2/skills/registry.py`, `harness/aether2/skills/invocation.py` | ported now (adapted) | copied `SKILL.md` directory scanning, shared frontmatter parsing concepts, realpath-backed duplicate detection, conditional path matching, explicit `loadedFrom`/source metadata, and write-once MCP builder registration | no managed/user/project auto-discovery walk, no legacy `/commands/` loader, no shell execution/substituteArguments/session-id injection, no settings/policy/bare-mode integration, no analytics/debug logging, no dynamic activation signal bus |
| `src/skills/bundledSkills.ts` | bundled skill registry | `harness/aether2/skills/registry.py` | ported now (bounded) | copied bundled skill definition/registration shape, safe reference-file extraction with path-traversal blocking, and deterministic materialization into ordinary skills | no shipped bundled skill content, no process-global init list, no Windows-specific flag handling, no lazy invocation wrapper around prompt generation |
| `src/skills/mcpSkillBuilders.ts` | skills + MCP bridge | `harness/aether2/skills/registry.py`, `harness/aether2/skills/loader.py` | ported now | copied the write-once registry for `create_skill_spec` + `parse_skill_frontmatter_fields` so future MCP skill discovery can reuse the same builders without a direct import cycle | no live MCP skill discovery yet; current bridge is metadata-only and local |
| `src/skills/bundled/index.ts` | bundled skill init | future skill init surface | inspected now | used only to classify provider/feature-flagged bundled content as explicitly out of scope for this slice | no bundled content auto-registration in Aether |
| `src/skills/bundled/verify.ts` | bundled skill example | `tests/test_aether2_skills.py` reference only | inspected now | used as a concrete reference for frontmatter-free bundled prompt registration shape | no public bundled prompt text ported |
| `src/skills/bundled/**` | bundled skill content | none in runtime slice | excluded/deferred | inventory-inspected as examples and explicit exclusions | provider/auth/telemetry/remote-agent/browser/app-specific content excluded from this slice |
| `src/components/skills/SkillsMenu.tsx` | UI-only | none | excluded | inventory-inspected | React/Ink UI excluded |
| `src/utils/hooks/registerFrontmatterHooks.ts` | skill/agent frontmatter hook bridge | `harness/aether2/skills/loader.py` | ported now (metadata-only adaptation) | copied the idea that frontmatter hooks are parsed into session-scope-ready matcher structures tied to a source name | no automatic registration or execution of frontmatter hook commands; metadata is retained visibly and must be explicitly consumed |
| `src/utils/hooks/registerSkillHooks.ts` | skill hook lifetime helper | future explicit skill invocation runtime | inspected now | used to bound the no-hidden-behavior decision: hook metadata is retained now, but registration/execution is intentionally deferred | no once-hook execution lifecycle yet |
| `src/types/command.ts` (`PromptCommand` skill fields) | skill metadata contract | `harness/aether2/skills/loader.py`, `harness/aether2/skills/registry.py` | ported now (adapted) | copied skill metadata fields such as `allowedTools`, `whenToUse`, `hooks`, `skillRoot`, `context`, `agent`, `paths`, `loadedFrom`, and user-facing-name behavior | no JSX/local-command/UI command variants in Python slice |

## Subagents

| TS source | Classification | Python target | Port status | Exact behavior copied/adapted | Simplified or deferred dependencies |
| --- | --- | --- | --- | --- | --- |
| `src/tools/AgentTool/loadAgentsDir.ts` | subagent registry core | `harness/aether2/agents/loader.py` | ported now (bounded adaptation) | copied deterministic markdown agent loading, frontmatter parsing for tool/skill/MCP refs, permission mode retention, hook metadata retention, `requiredMcpServers` filtering, and active-agent precedence concepts | built-in agent catalog, plugin policy gates, memory prompt injection, and source-discovery walks outside a provided directory remain deferred |
| `src/tools/AgentTool/runAgent.ts` | subagent runtime core | `harness/aether2/agents/runtime.py` | ported now (bounded adaptation) | copied explicit per-agent skill preload resolution, visible MCP-ref handling, permission-mode/hook metadata retention, parent-visible unresolved risks, and the requirement that worker execution stay explicit instead of silently backgrounding | no live query loop, provider/model routing, transcript recording, hook execution, MCP connection startup, or prompt-cache plumbing |
| `src/tools/AgentTool/AgentTool.tsx` | subagent tool + orchestration/UI boundary | `harness/aether2/agents/task.py`, `harness/aether2/agents/runtime.py`, `harness/aether2/agents/handoff.py` | ported now (bounded adaptation) | copied the bounded task brief concept, explicit worker handoff/result contract, and "no silent background swarms" behavior into a deterministic local/fake runtime boundary | tool prompt text, React/Ink rendering, coordinator/team spawn flows, background task registration, and worktree/remote launch modes excluded |
| `src/tools/AgentTool/agentToolUtils.ts` | subagent tool-resolution + handoff helpers | `harness/aether2/agents/runtime.py`, `harness/aether2/agents/handoff.py` | ported now (bounded adaptation) | copied explicit allowed-tool resolution checks, handoff/result normalization ideas, and visible classification of unresolved worker outcomes | YOLO classifier, async lifecycle helpers, background summarization, and SDK progress plumbing deferred |
| `src/tools/AgentTool/prompt.ts` | subagent prompt contract | `harness/aether2/agents/task.py`, eval/docs only | ported now (bounded adaptation) | copied the qualitative constraint that subagent work must be explicitly scoped and clearly briefed, but kept it as structured task-packet fields rather than a model-facing prompt blob | fork-specific examples, subscription heuristics, and interactive tool-description text excluded |
| `src/tools/AgentTool/builtInAgents.ts` | built-in agent registry | none in this slice | deferred | inventory-inspected to separate reusable runtime shape from bundled prompt content | built-in agent prompt bodies/content remain outside the public-ready substrate slice |
| `src/tools/AgentTool/built-in/**` | bundled subagent content | none in this slice | excluded/deferred | inventory-inspected as prompt/content examples only | Claude-branded built-ins, statusline helpers, verification prompt content, and memory-specific prompt bodies excluded |
| `src/tools/AgentTool/agentMemory.ts` | memory prompt augmentation | none in this slice | deferred | inspected to classify memory as additive prompt content rather than loader/runtime core | no persistent agent memory or snapshot prompts in the public slice |
| `src/tools/AgentTool/agentMemorySnapshot.ts` | memory snapshot runtime | none | deferred | inventory-inspected | memory snapshot init/update flow deferred |
| `src/tools/AgentTool/forkSubagent.ts` | forked subagent cache-sharing/runtime | none | excluded/deferred | inspected only to separate fork-specific continuation semantics from the bounded local/fake slice | fork cache-sharing, worktree notices, recursive fork guards, and fork prompt boilerplate excluded |
| `src/tools/AgentTool/resumeAgent.ts` | resume sidechain runtime | none | deferred | inventory-inspected | transcript resume/replay wiring deferred |
| `src/tools/AgentTool/constants.ts` | tool naming/constants | `harness/aether2/agents/task.py`, docs only | ported now (adapted) | copied the explicit idea that worker launches are a named, bounded surface rather than an implicit planning side effect | legacy aliases and UI-specific constants excluded |
| `src/tools/AgentTool/UI.tsx`, `src/tools/AgentTool/agentDisplay.ts`, `src/tools/AgentTool/agentColorManager.ts` | UI-only presentation | none | excluded | inventory-inspected | React/Ink display/color presentation excluded |
| `src/tasks/LocalAgentTask/LocalAgentTask.tsx` | subagent task runtime | `harness/aether2/agents/task.py`, `harness/aether2/agents/handoff.py` | ported now (bounded adaptation) | copied the explicit local task packet + completion/failure handoff boundary, including validation commands, files changed, and external-state reporting | task panel state, abort controllers, notifications, progress trackers, and transcript mirroring excluded |
| `src/tasks/InProcessTeammateTask/InProcessTeammateTask.tsx` | teammate lifecycle boundary | `harness/aether2/agents/runtime.py`, `harness/aether2/agents/handoff.py` | ported now (bounded adaptation) | copied the requirement that in-process worker results be routed back through a visible handoff instead of disappearing into background state | mailbox injection, idle callbacks, plan-mode approval flow, and AsyncLocalStorage teammate identity deferred |
| `src/tasks/InProcessTeammateTask/types.ts` | teammate task state contract | `harness/aether2/agents/handoff.py`, `harness/aether2/agents/task.py` | ported now (bounded adaptation) | copied the notion that worker identity/ownership/progress state must be explicit structured data | UI transcript caps, spinner verbs, and live task-state mutability deferred |
| `src/tasks/RemoteAgentTask/RemoteAgentTask.tsx` | remote/proprietary | none | excluded | inventory-inspected as remote surface | remote session flow excluded |
| `src/commands/agents/index.ts` | agent command entry | docs only | inspected now | used only to classify `/agents` as a management/UI shell rather than runtime core | JSX command surface deferred |
| `src/commands/agents/agents.tsx` | UI-only command entry | none | excluded | inventory-inspected wrapper around agents menu | React/Ink UI excluded |
| `src/components/agents/**` | UI-only | none | excluded | inventory-inspected as editor/list/wizard surfaces | React/Ink UI excluded |

## Python Ownership For This Slice

| Python target | Ownership in this slice |
| --- | --- |
| `harness/aether2/hooks/lifecycle.py` | canonical hook event/result/decision primitives |
| `harness/aether2/hooks/registry.py` | canonical session hook registry |
| `harness/aether2/hooks/builtins.py` | canonical built-in hook helpers for tests and policy smoke |
| `harness/aether2/skills/loader.py` | canonical filesystem skill discovery, frontmatter parsing, and MCP-builder registration |
| `harness/aether2/skills/registry.py` | canonical repo-local + bundled skill registry, deterministic collision handling, and MCP-linked metadata retention |
| `harness/aether2/skills/invocation.py` | canonical visible skill context rendering for model-facing prefix messages |
| `harness/aether2/skills/__init__.py` | public skill exports |
| `harness/aether2/agents/loader.py` | canonical filesystem agent discovery, frontmatter parsing, and MCP/skill/permission metadata retention |
| `harness/aether2/agents/task.py` | canonical bounded worker task packet with scope, evidence, ownership, and explicit no-background defaults |
| `harness/aether2/agents/handoff.py` | canonical worker handoff/result evidence surface |
| `harness/aether2/agents/runtime.py` | canonical local/fake worker preparation and execution boundary with visible skill/MCP resolution |
| `harness/aether2/agents/__init__.py` | public agent exports |
| `harness/aether2/tools/permissions.py` | canonical permission rule/policy/decision engine |
| `harness/aether2/tools/native.py` | canonical native tool schemas plus generic hook/permission dispatch wrapper |
| `harness/aether2/tools/mcp.py` | canonical MCP config/state/schema-mapping/fake-local runtime substrate |
| `harness/aether2/tools/registry.py` | canonical native + MCP registration/discovery/invocation boundary |
| `harness/aether2/control/loop.py` | receipts/trace integration and loop wiring with optional registry-aware schemas |
| `harness/aether2/__init__.py`, `harness/aether2/tools/__init__.py` | public exports |
| `runner/aether2/skills.py`, `runner/aether2/__init__.py` | runner compatibility exports for the new skill surface |

## Next Dependency-Ready Direct Port Slice

- Direct-port dependency chain status: ready to move to AI-native engineering showcase work.
- Reason:
  - hooks + permissions, MCP, skills, and the explicit local/fake subagent
    loader/task/handoff/runtime boundary now exist as reusable public-facing
    substrate;
  - remaining quarantined TS surfaces are either UI-only, remote/auth/telemetry
    proprietary, or bundled prompt content rather than dependency-critical
    runtime substrate;
  - future work can focus on AI-native engineering/eval integration or on
    optional bounded follow-ups such as built-in agent content treatment, not a
    missing direct-port dependency.
