# Ceiling: mcp_registry_contract (v2)

## What a perfect solution does

Rebuilds both bundle files from the sources in `mcp/` and `challenge.txt`:

1. Reads `mcp/registry.json`. The `active` entry's manifest lists `echo_payload` and `broken_schema`, both
   enabled. The `retired` entry (`mcp/legacy/qa_server.2026-08.json`) lists `echo_payload` again.
2. Discovery: only active entries contribute. `echo_payload` maps. `broken_schema` uses the scalar type
   `bytes`, which is not valid, so it is rejected with `mcp_schema_mapping_error`. The list is
   `["mcp__qa_server__echo_payload"]`. `echo_payload` is listed by two entries, so it is also in
   `repeat_discovered_tool_names`.
3. Schema mapping: the active schema file (not the `v0` file) keeps `type`, `properties` reduced to type,
   `required` and `additionalProperties`. `count` is kept. Titles and descriptions are dropped.
4. Invocation codes: from `mcp/reason_codes.json`, not the retired names in `docs/legacy_reason_codes.md`.
   Success maps to null.
5. Hook trace: the enabled hooks in order (`stop` is disabled). The `permission_request` hook points at
   `permission_policy.json`, which allows `echo_payload`. The `.previous` policy is ignored.
6. Native regression: the latest run by `started` (`nr-2026-10-13-02`), not the September failure.
7. Challenge: `challenge.txt` stripped, prefixed with `payload=`.
8. The trace carries six sections and no `bundle_contract`.

## Why each known-bad state is wrong

- `discovery_includes_broken_schema.sh`: adds the rejected tool to the discovered list. `discovery_mismatch`.
- `schema_mapping_drops_count.sh`: drops `count` from the mapped parameters. `schema_mapping_mismatch`.
- `timeout_and_error_collapsed.sh`: uses the retired `runtime_error` and `dispatch_error` names. `invocation_results_mismatch`.
- `challenge_response_missing.sh`: writes the default smoke token instead of reading `challenge.txt`. `challenge_response_mismatch`.
- `hook_permission_denied.sh`: records `deny` (the previous policy's behaviour). `hook_permission_trace_mismatch`.
- `native_read_regressed.sh`: records the September run's failures. `native_regression_mismatch`.
- `trace_timeout_code_diverges.sh`: the audit is right but the trace is not. `invocation_results_mismatch`.
- `audit_truncated.sh`: drops `bundle_contract`. `audit_section_missing`.

## Careless controls

- `do_nothing.sh`: `audit_section_missing` (the stale placeholders stay).
- `fake_it.sh`: right shape, values from the retired manifest and legacy codes. `discovery_mismatch`.
- `skip_check.sh`: copies the previous policy's default without reading the active policy. `hook_permission_trace_mismatch`.
- `wrong_target.sh`: moves the bundle into `out/`. `missing_audit_file`.
- `half_done.sh`: writes only part of the audit and removes the stale trace. `missing_trace_file`.

## Grader expectations

- Reference: `passed: true`.
- Untouched workspace: the stale placeholders fail with section-missing codes and `other_file_modified` is not raised.
- Every known-bad fails with its `# expect:` code in `reasons`.
