#!/usr/bin/env bash
# expect: unresolved_risks_hidden
# Reports the worker's unresolved risks as not surfaced to the parent.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("subagent_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["visibility"]["parent_visible_unresolved_risks"] = False
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
