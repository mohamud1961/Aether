#!/usr/bin/env bash
# expect: schema_mapping_mismatch
# Maps the echo schema but drops the optional count property, which the schema file defines.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
for name in ("mcp_audit.json", "mcp_registry_trace.json"):
    path = Path(name)
    doc = json.loads(path.read_text(encoding="utf-8"))
    del doc["schema_mapping"]["parameters"]["properties"]["count"]
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
