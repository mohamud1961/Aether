#!/usr/bin/env bash
# expect: hook_permission_trace_mismatch
# Takes the previous policy file (deny by default) as the current one and records deny for echo_payload.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
for name in ("mcp_audit.json", "mcp_registry_trace.json"):
    path = Path(name)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["hook_permission_trace"]["permission_behavior"] = "deny"
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
