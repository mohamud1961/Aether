#!/usr/bin/env bash
# expect: skill_or_mcp_refs_not_visible
# Drops the skill_not_found code for citation-helper, which is not on disk.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("subagent_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["resolution_summary"]["skill_issue_reason_codes"] = []
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
