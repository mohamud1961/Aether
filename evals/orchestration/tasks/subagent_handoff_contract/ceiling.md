# Ceiling: subagent_handoff_contract (v2)

## What a perfect solution does

Derives `subagent_audit.json` from the workspace sources:

1. Loads `agents/*.md`. `retired-runner.md` (`status: retired`) is skipped. The rest are sorted by name:
   `research-auditor`, then `support-runner`.
2. `frontmatter_summary` is keyed by agent. `research-auditor` is background, `plan` mode, has a hook, and declares
   `qa-server`, an inline `inline-probe`, and skills `alpha-skill` and `citation-helper`. `support-runner` is
   foreground, `default` mode, no hooks, declares `qa-server` and `ticket-api`.
3. Resolution: `alpha-skill` resolves to `skills/alpha-skill/`. `citation-helper` gives `skill_not_found`.
   `qa-server` resolves through `mcp/servers.json`. `ticket-api` is not in the registry, so it gives
   `required_mcp_server_missing`. `inline-probe` is inline, so it gives `agent_inline_mcp_unresolved`.
4. `task_packet`: `ownership` is absent from `handoff/task_packet.json`, so it is `false`. The other five fields are present.
5. `handoff` comes from `worker_report.json`: status `partial`, with files, validation and risks present, and external state touched.
6. Visibility: the parent inbox surfaces the same risk, and lists the background run `research-auditor`.
7. Leaves the sources byte-identical. The stale placeholder is replaced.

## Why each known-bad state is wrong

- `agent_order_reversed.sh`: reverses the agent order. `agent_loader_not_deterministic`.
- `agent_order_flag_cleared.sh`: keeps the order but clears the flag. `agent_loader_not_deterministic`.
- `background_flag_dropped.sh`: records research-auditor as foreground. `agent_frontmatter_parse_mismatch`.
- `missing_skill_not_reported.sh`: drops `skill_not_found`. `skill_or_mcp_refs_not_visible`.
- `risks_hidden_from_parent.sh`: says the parent cannot see the risks. `unresolved_risks_hidden`.
- `background_execution_assumed.sh`: clears the silent-execution check. `silent_background_execution_assumed`.
- `handoff_risks_omitted.sh`: drops unresolved risks from the handoff. `handoff_contract_missing`.
- `scope_field_missing.sh`: marks a present packet field as missing. `task_packet_contract_missing`.

## Careless controls

- `do_nothing.sh`: the placeholder's reversed order and cleared flag stay. `agent_loader_not_deterministic`.
- `fake_it.sh`: all-true values with plausible names, no reading. `agent_frontmatter_parse_mismatch`.
- `skip_check.sh`: takes `ticket-api` as resolved without checking the registry. `skill_or_mcp_refs_not_visible`.
- `wrong_target.sh`: writes the record into `agents/`, leaving the placeholder. `agent_loader_not_deterministic`.
- `half_done.sh`: loader and frontmatter written, the placeholder handoff stays. `handoff_contract_missing`.

## Grader expectations

- Reference: `passed: true`.
- Placeholder: fails on loader order, frontmatter, resolution, packet, handoff and visibility.
- Every known-bad fails with its `# expect:` code in `reasons`.
