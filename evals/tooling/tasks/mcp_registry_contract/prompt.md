# Rebuild the MCP registry contract bundle

You are in the workspace root. The bundle here, `mcp_audit.json` and `mcp_registry_trace.json`, came from an
earlier run and no longer matches the registry. Rebuild both files from the registry sources under `mcp/`.
The challenge token is in `challenge.txt`.

No MCP server runs in this workspace. The echo tool `mcp__qa_server__echo_payload` returns its input text
prefixed with `payload=`, so `challenge_response` is that prefix followed by the token.

## Files

`mcp_audit.json` is a JSON object with these top-level keys: `discovery`, `schema_mapping`,
`invocation_results`, `hook_permission_trace`, `native_regression`, `bundle_contract` and `challenge_response`.

`mcp_registry_trace.json` is a JSON object with the same keys except `bundle_contract`.

Field layout:

- `discovery`: `discovered_tool_names`, `repeat_discovered_tool_names`, `schema_issue_reason_codes` (lists).
- `schema_mapping`: `qualified_name` and `parameters` (the mapped input schema).
- `invocation_results`: `success_reason_code`, `timeout_reason_code`, `error_reason_code`,
  `unavailable_reason_code`, `schema_mapping_reason_code`.
- `hook_permission_trace`: `events` (list) and `permission_behavior`.
- `native_regression`: `write_file_exit_code`, `read_file_exit_code`, `read_stdout_contains`.
- `bundle_contract`: `required_files` (list) and `trace_file`, as the bundle spec states them.
- `challenge_response`: a string.

## Rules

- The discovery and mapping rules are in `mcp/docs/discovery.md`. Some notes in the tree predate the
  current registry, so check them against the sources.
- Both files are JSON objects in the workspace root. They must agree with each other on every key they share,
  and carry the same `challenge_response`.
- Do not change anything under `mcp/` or `challenge.txt`.

Public dataset identifier: harness-evals-public-2bd939ba1f6b2c88.
