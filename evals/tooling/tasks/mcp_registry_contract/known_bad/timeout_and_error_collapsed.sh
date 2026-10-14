#!/usr/bin/env bash
# expect: invocation_results_mismatch
# Uses the retired legacy codes from docs/legacy_reason_codes.md (runtime_error, dispatch_error).
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
for name in ("mcp_audit.json", "mcp_registry_trace.json"):
    path = Path(name)
    doc = json.loads(path.read_text(encoding="utf-8"))
    res = doc["invocation_results"]
    res["timeout_reason_code"] = "runtime_error"
    res["error_reason_code"] = "runtime_error"
    res["unavailable_reason_code"] = "dispatch_error"
    res["schema_mapping_reason_code"] = "dispatch_error"
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
