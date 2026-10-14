#!/usr/bin/env bash
# expect: agent_loader_not_deterministic
# Keeps the order but clears the determinism flag.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("subagent_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["agent_order_is_deterministic"] = False
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
