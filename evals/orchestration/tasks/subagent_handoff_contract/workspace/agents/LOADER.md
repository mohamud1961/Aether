# Agent loader rules (v2)

- Every `agents/*.md` file with a frontmatter block is read. Files with `status: retired` are skipped.
- Loaded agents are returned sorted by their `name`. File names do not decide order.
- `skills` entries resolve to `skills/<name>/SKILL.md`. A missing one gives `skill_not_found`.
- `mcpServers` entries that are strings name a server in `mcp/servers.json`. A string with no enabled server gives
  `required_mcp_server_missing`. Inline objects are not resolved against the registry and give `agent_inline_mcp_unresolved`.
- `hooks_retained` is true when the agent declares at least one hook.
- Background agents run detached. The parent inbox must list each one under `background_runs_reported`.
