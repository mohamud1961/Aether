#!/usr/bin/env bash
# expect: skill_context_not_visible_or_bounded
# Reports the visible block as truncated and not recorded in the prefix.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

path = Path("skill_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["visible_context"]["truncated"] = True
audit["visible_context"]["recorded_in_prefix"] = False
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
