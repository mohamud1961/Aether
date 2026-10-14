#!/usr/bin/env bash
# expect: hook_permission_trace_mismatch
# Takes the previous permission policy's deny default as the current behaviour and never reads the active policy.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
policy = json.loads(Path("mcp/hooks/permission_policy.previous.json").read_text(encoding="utf-8"))
hook = {"events": ["permission_request", "pre_tool_use", "post_tool_use"], "permission_behavior": policy["default_behavior"]}
for name in ("mcp_audit.json", "mcp_registry_trace.json"):
    Path(name).write_text(json.dumps({"hook_permission_trace": hook}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
