#!/usr/bin/env bash
# expect: skill_missing_reason_codes_absent
# Drops the skill_not_found code for the missing reference.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

path = Path("skill_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["selection_reason_codes"]["missing"] = []
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
