# Task card: MCP registry contract bundle (v2)

Admission: **capability**. Controls test the v2 design. They do not establish parity with the original trace contract.

## Design (v2)

- The bundle is derived from the registry sources, not copied from an answer file.
- Two hops: `mcp/registry.json` -> manifests -> `schemas/`; hooks -> permission policy.
- Decoys: a retired manifest listing the same tool (duplicate), a `v0` schema, `permission_policy.previous.json`,
  a September failing run in `runs.ndjson`, `challenge.txt.bak`.
- Stale docs: `mcp/docs/discovery.md` has a superseded line; `mcp/docs/legacy_reason_codes.md` lists retired codes.
- Trap: `broken_schema` is enabled but does not map.
- Pristine `mcp/` and `challenge.txt` are sealed by hash.

## Controls

- Known-bad: 8 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| discovery_mismatch | known_bad discovery_includes_broken_schema; careless fake_it |
| schema_mapping_mismatch | known_bad schema_mapping_drops_count |
| invocation_results_mismatch | known_bad timeout_and_error_collapsed, trace_timeout_code_diverges |
| challenge_response_mismatch | known_bad challenge_response_missing |
| hook_permission_trace_mismatch | known_bad hook_permission_denied; careless skip_check |
| native_regression_mismatch | known_bad native_read_regressed |
| audit_section_missing | known_bad audit_truncated |
| audit_section_missing | careless do_nothing |
| missing_audit_file | careless wrong_target |
| missing_trace_file | careless half_done |

Trace-dependent checks (trace-level event order) are not established by this final-state grader.
