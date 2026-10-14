# Discovery and mapping rules

Discovery reads the registry (`mcp/registry.json`) and each entry's manifest.

- A tool is listed when its manifest entry has `enabled: true`.
- Only entries with status `active` contribute discovered tools. Qualified names are
  `mcp__<server>__<tool>`. The discovered list is unique and sorted.
- A listed tool whose schema does not map is rejected with the `schema_mapping` outcome code. A schema maps when
  its `type` is `object` and each property has one of the scalar types `string`, `integer`, `number` or `boolean`.
- `repeat_discovered_tool_names`: qualified names listed by more than one registry entry, whatever the status. Sorted.
- `schema_mapping` describes the first discovered tool in sorted order. Its parameters keep only `type`,
  `properties` (each reduced to its `type`), `required` and `additionalProperties`. Descriptions and titles are dropped.
- Permission behaviour for that tool comes from the policy that the `permission_request` hook points at:
  a rule for the tool name if one exists, else the policy default.
- Hook events are the enabled hooks, in their listed order.

Note (2026-06): every registry entry is discovered. Superseded by the active-only rule above.
