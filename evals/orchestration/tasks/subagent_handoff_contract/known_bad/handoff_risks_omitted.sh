#!/usr/bin/env bash
# expect: handoff_contract_missing
# Reports the worker handoff without unresolved risks.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("subagent_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["handoff"]["unresolved_risks"] = False
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
