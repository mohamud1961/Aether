#!/usr/bin/env bash
# expect: discovery_mismatch
# Writes both files with the right shape from the retired manifest and legacy codes, without deriving anything from the active registry.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
discovery = {
    "discovered_tool_names": ["mcp__qa_server__echo_payload", "mcp__qa_server__broken_schema"],
    "repeat_discovered_tool_names": [],
    "schema_issue_reason_codes": [],
}
trace = {
    "discovery": discovery,
    "schema_mapping": {"qualified_name": "mcp__qa_server__echo_payload", "parameters": {"type": "object", "properties": {"payload": {"type": "string"}}}},
    "invocation_results": {"success_reason_code": None, "timeout_reason_code": "runtime_error", "error_reason_code": "runtime_error", "unavailable_reason_code": "dispatch_error", "schema_mapping_reason_code": "dispatch_error"},
    "hook_permission_trace": {"events": ["pre_tool_use", "post_tool_use"], "permission_behavior": "deny"},
    "native_regression": {"write_file_exit_code": 0, "read_file_exit_code": 0, "read_stdout_contains": "hello"},
    "challenge_response": "payload=default_smoke_challenge",
}
audit = dict(trace, bundle_contract={"required_files": ["mcp_audit.json", "mcp_registry_trace.json"], "trace_file": "mcp_registry_trace.json"})
Path("mcp_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
Path("mcp_registry_trace.json").write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
