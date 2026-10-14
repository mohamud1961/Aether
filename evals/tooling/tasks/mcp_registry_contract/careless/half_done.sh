#!/usr/bin/env bash
# expect: missing_trace_file
# Writes the discovery section of the audit from the active manifest, deletes the stale trace file, and stops.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
audit = {"discovery": {
    "discovered_tool_names": ["mcp__qa_server__echo_payload"],
    "repeat_discovered_tool_names": ["mcp__qa_server__echo_payload"],
    "schema_issue_reason_codes": ["mcp_schema_mapping_error"],
}}
Path("mcp_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
rm -f mcp_registry_trace.json
