#!/usr/bin/env bash
# expect: hook_order_mismatch
# Reference audit with the event order copied from the SDK 2.1 summary: permission_request first.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("policy_audit.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["events"] = ["permission_request", "pre_tool_use", "post_tool_use"]
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
