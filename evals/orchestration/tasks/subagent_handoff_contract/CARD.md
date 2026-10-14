# Task card: subagent handoff contract audit (v2)

Admission: **capability**. Controls test the v2 design. They do not establish parity with the original trace contract.

## Design (v2)

- The record is derived from agent definitions, a loader rule file, skill and MCP registries, a task packet, a worker report and a parent inbox.
- Decoys: a retired agent definition, an inline MCP server, a missing skill, a required MCP server not in the registry.
- Stale placeholder with the old loader order and cleared flags.
- Source files are sealed by hash; the reference uses no `$TASK_ROOT`.

## Controls

- Known-bad: 8 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| agent_loader_not_deterministic | known_bad agent_order_reversed, agent_order_flag_cleared; careless do_nothing, wrong_target |
| agent_frontmatter_parse_mismatch | known_bad background_flag_dropped; careless fake_it |
| skill_or_mcp_refs_not_visible | known_bad missing_skill_not_reported; careless skip_check |
| unresolved_risks_hidden | known_bad risks_hidden_from_parent |
| silent_background_execution_assumed | known_bad background_execution_assumed |
| handoff_contract_missing | known_bad handoff_risks_omitted; careless half_done |
| task_packet_contract_missing | known_bad scope_field_missing |
