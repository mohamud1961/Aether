#!/usr/bin/env bash
# expect: native_regression_mismatch
# Reports the older September run, where the read failed with exit code 1.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
for name in ("mcp_audit.json", "mcp_registry_trace.json"):
    path = Path(name)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if "native_regression" in doc:
        doc["native_regression"] = {"write_file_exit_code": 1, "read_file_exit_code": 1, "read_stdout_contains": "probe"}
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
