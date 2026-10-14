#!/usr/bin/env bash
# expect: agent_frontmatter_parse_mismatch
# Records research-auditor as foreground, dropping its background: true from the frontmatter summary.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("subagent_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["frontmatter_summary"]["research-auditor"]["background"] = False
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
