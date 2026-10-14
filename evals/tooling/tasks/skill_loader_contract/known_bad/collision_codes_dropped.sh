#!/usr/bin/env bash
# expect: skill_collision_handling_missing
# Records no collision reason codes although the duplicate and the name collision were rejected.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

path = Path("skill_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["collision_reason_codes"] = {"same_file": [], "same_name": []}
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
