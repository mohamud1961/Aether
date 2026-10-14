#!/usr/bin/env bash
# expect: skill_or_mcp_refs_not_visible
# Takes the first MCP name it sees, ticket-api, as resolved, and never checks the registry.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
path = Path("subagent_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["resolution_summary"]["resolved_mcp_servers"] = ["ticket-api"]
audit["resolution_summary"]["mcp_issue_reason_codes"] = []
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
