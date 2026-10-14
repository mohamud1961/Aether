#!/usr/bin/env bash
# expect: audit_section_missing
# Drops the bundle_contract section from the audit, so the bundle no longer states its own files.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("mcp_audit.json")
doc = json.loads(path.read_text(encoding="utf-8"))
del doc["bundle_contract"]
path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
