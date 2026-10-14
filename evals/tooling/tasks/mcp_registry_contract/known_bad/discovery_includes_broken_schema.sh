#!/usr/bin/env bash
# expect: discovery_mismatch
# Lists the broken_schema tool as discovered, although its schema does not map.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
for name in ("mcp_audit.json", "mcp_registry_trace.json"):
    path = Path(name)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["discovery"]["discovered_tool_names"] = ["mcp__qa_server__broken_schema", "mcp__qa_server__echo_payload"]
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
