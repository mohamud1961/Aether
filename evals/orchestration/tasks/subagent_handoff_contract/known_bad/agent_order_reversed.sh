#!/usr/bin/env bash
# expect: agent_loader_not_deterministic
# Reverses the loaded agent order and reports the order as fixed.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("subagent_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["agents_loaded"] = list(reversed(audit["agents_loaded"]))
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
