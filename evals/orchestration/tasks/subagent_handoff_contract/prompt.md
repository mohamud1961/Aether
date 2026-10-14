# Audit the subagent loader and the handoff record

You are in the working directory. It holds `subagent_audit.json`, a record of how the subagent loader and the
handoff contract behaved for the last run. The copy here is a placeholder with unset values. Replace it with the
record the sources support.

The sources are under `agents/` (agent definitions and the loader rules in `agents/LOADER.md`), `skills/`,
`mcp/`, `handoff/` (the task packet, the worker report and the parent inbox) and `loader/run.log`.

`subagent_audit.json` must keep these top-level sections:

- `agents_loaded`: the names of the loaded agents, in the order the loader returns them.
- `agent_order_is_deterministic`: `true` only if that order is fixed by the loader rules.
- `frontmatter_summary`: one entry per loaded agent, keyed by agent name, with `background`,
  `hooks_retained`, `mcp_servers_retained`, `permission_mode` and `skills_retained`.
- `resolution_summary`: the skill and MCP references that resolved, and the reason codes for those that did not.
- `task_packet`: one boolean per required field of the bounded worker task packet (`objective`, `scope`,
  `files_to_touch`, `ownership`, `exit_criteria`, `evidence_expectations`). A field is `true` only when the packet
  carries it with a non-empty value.
- `handoff`: the worker's structured handoff (`status`, `files_changed`, `validation_commands`, `external_state`,
  `unresolved_risks`), each a boolean or status as the report supports.
- `visibility`: `parent_visible_unresolved_risks` and `no_silent_background_execution`.

Unresolved risks must stay visible to the parent. The record must not assume a worker ran silently in the background.
Write only `subagent_audit.json`. Do not add keys. Do not change anything else in the workspace.

Public dataset identifier: harness-evals-public-498431365157d0ed.
