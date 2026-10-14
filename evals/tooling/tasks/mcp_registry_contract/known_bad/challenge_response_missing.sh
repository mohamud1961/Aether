#!/usr/bin/env bash
# expect: challenge_response_mismatch
# Falls back to the default smoke token instead of reading challenge.txt.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
for name in ("mcp_audit.json", "mcp_registry_trace.json"):
    path = Path(name)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["challenge_response"] = "payload=default_smoke_challenge"
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
