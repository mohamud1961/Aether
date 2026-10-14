#!/usr/bin/env bash
# expect: silent_background_execution_assumed
# Clears no_silent_background_execution although the parent inbox lists the background run.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("subagent_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["visibility"]["no_silent_background_execution"] = False
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
