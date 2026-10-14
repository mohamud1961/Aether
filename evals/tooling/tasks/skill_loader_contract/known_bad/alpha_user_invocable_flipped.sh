#!/usr/bin/env bash
# expect: skill_frontmatter_parse_mismatch
# Parses alpha-skill with user_invocable true, as the legacy duplicate file says.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

path = Path("skill_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["frontmatter_summary"]["alpha-skill"]["user_invocable"] = True
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
