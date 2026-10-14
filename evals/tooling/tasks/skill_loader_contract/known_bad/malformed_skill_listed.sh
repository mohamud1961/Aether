#!/usr/bin/env bash
# expect: skill_discovery_set_mismatch
# Lists broken-skill as discovered, although its frontmatter has no closing fence.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

path = Path("skill_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["skills_discovered"].append("broken-skill")
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
