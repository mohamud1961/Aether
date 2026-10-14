#!/usr/bin/env bash
# expect: invocation_results_mismatch
# Leaves the audit correct, but the trace file carries a different timeout code.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("mcp_registry_trace.json")
doc = json.loads(path.read_text(encoding="utf-8"))
doc["invocation_results"]["timeout_reason_code"] = "mcp_tool_error"
path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
