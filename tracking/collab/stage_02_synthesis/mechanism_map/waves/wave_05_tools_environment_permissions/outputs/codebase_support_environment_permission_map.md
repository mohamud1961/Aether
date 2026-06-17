# Wave 05 Codebase Support: Environment and Permission Map

Purpose: bounded support artifact for environment discovery, sandbox boundaries, approval controls, and cwd/workdir discipline.

## Mechanism slices

## 1) Environment discovery and preconditions

- deepagents:
  - Observation: local context middleware runs a detection script through backend `execute`/`aexecute` and injects results into system prompt.
  - Evidence: `research/sources/codebases/deepagents/libs/cli/deepagents_cli/local_context.py`
- KIRA:
  - Observation: settings model centralizes workspace, MCP enable flags, browser toggles, and command policy defaults.
  - Evidence: `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/settings.py`
- a-evolve:
  - Observation: seed environment-discovery skill explicitly scripts tool/language/filesystem checks in `/app` and installed binaries.
  - Evidence: `research/sources/codebases/a-evolve/seed_workspaces/terminal/skills/environment-discovery/SKILL.md`

## 2) Execution and sandbox boundaries

- deepagents:
  - Observation: local shell backend explicitly warns there is no sandboxing and uses host `subprocess.run(..., shell=True, cwd=...)`.
  - Evidence: `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/local_shell.py`
  - Observation: middleware keeps `execute` tool but runtime-checks `SandboxBackendProtocol` and errors/filters when unsupported.
  - Evidence: `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/filesystem.py`
- KIRA:
  - Observation: process manager shells with `shell=True`, but passes command through `check_command` and resolve-cwd validation.
  - Evidence: `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_manager.py`
- a-evolve:
  - Observation: terminal and MCP families lean on Docker container lifecycle wrappers; shell/python are `docker exec` based.
  - Evidence: `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/tools.py`, `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/docker_env.py`, `research/sources/codebases/a-evolve/agent_evolve/agents/mcp/docker_env.py`

## 3) Permission and approval boundaries

- deepagents:
  - Observation: HITL interrupt map gates `execute`, file writes/edits, web search/fetch, and task delegation.
  - Evidence: `research/sources/codebases/deepagents/libs/cli/deepagents_cli/agent.py`
  - Observation: project MCP stdio servers are trust-gated by config fingerprint; untrusted stdio servers are filtered.
  - Evidence: `research/sources/codebases/deepagents/libs/cli/deepagents_cli/mcp_trust.py`, `research/sources/codebases/deepagents/libs/cli/deepagents_cli/mcp_tools.py`
- KIRA:
  - Observation: allow/deny/ask command policy is threaded through bash tool and background process manager.
  - Evidence: `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/engine.py`, `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_manager.py`
  - Observation: alternate KIRA-Slack agent uses `permission_mode="bypassPermissions"` with explicit disallowed tool patterns.
  - Evidence: `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/bot_call_detector/agent.py`
- a-evolve:
  - Observation: terminal baseline lacks strong first-class approval gate in tool wrappers; control is mostly via container and task-level tool filtering.
  - Evidence: `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/tools.py`, `research/sources/codebases/a-evolve/agent_evolve/agents/mcp/agent.py`

## 4) CWD/workdir/path/process discipline

- deepagents:
  - Observation: system prompt and execute docs force absolute-path doctrine and discourage `cd`; `validate_path` rejects traversal and windows absolute paths.
  - Evidence: `research/sources/codebases/deepagents/libs/cli/deepagents_cli/agent.py`, `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/filesystem.py`, `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/utils.py`
- KIRA:
  - Observation: process manager defaults cwd to workspace and rejects invalid/non-dir resolved paths.
  - Evidence: `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/process_manager.py`
  - Observation: files MCP resolves relative paths under workspace (`KIRACLAW_WORKSPACE_DIR`).
  - Evidence: `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/files_mcp_tools.py`
- a-evolve:
  - Observation: terminal prompt states each bash call is independent and requires explicit chaining; container exec APIs accept optional workdir.
  - Evidence: `research/sources/codebases/a-evolve/seed_workspaces/terminal/prompts/system.md`, `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/docker_env.py`

## 5) Browser and MCP substrate (do not over-read as safety proof)

- KIRA:
  - Observation: browser MCP server wiring is feature-flagged and includes profile/output paths, but this by itself is not a permission doctrine.
  - Evidence: `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/settings.py`, `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/mcp_runtime.py`
- deepagents:
  - Observation: MCP support distinguishes stdio vs remote, performs config validation and trust filtering, then merges configs.
  - Evidence: `research/sources/codebases/deepagents/libs/cli/deepagents_cli/mcp_tools.py`, `research/sources/codebases/deepagents/libs/cli/deepagents_cli/mcp_trust.py`

## Archive-pressure and visibility caveat

- claw-code quarantine exposes mirrored tool/permission snapshots and simulated execution summaries, but README states it is not full runtime-equivalent replacement.
- Evidence: `research/sources/codebases/quarantine/claw-code/src/tools.py`, `research/sources/codebases/quarantine/claw-code/src/runtime.py`, `research/sources/codebases/quarantine/claw-code/README.md`

## Confidence posture for this support artifact

- High confidence: source-backed per-file observations above.
- Medium confidence: cross-family unification claims until full trajectory + contradiction pressure merge is complete.
- Low confidence: any claim that would require treating quarantine snapshots or no-source BigAI behavior as implementation-equivalent source.
