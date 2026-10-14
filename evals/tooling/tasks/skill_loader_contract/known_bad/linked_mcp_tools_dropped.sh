#!/usr/bin/env bash
# expect: skill_metadata_not_retained_safely
# Loses the MCP tool linked from tool-linked and reports no hook matchers.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

path = Path("skill_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["metadata_retention"]["linked_mcp_tools"] = []
audit["metadata_retention"]["hook_matcher_count"] = 0
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
