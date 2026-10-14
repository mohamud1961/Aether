#!/usr/bin/env bash
# expect: skill_discovery_not_deterministic
# Reverses the discovered order and reports the order as not fixed by the loader.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

path = Path("skill_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["skills_discovered"] = list(reversed(audit["skills_discovered"]))
audit["skill_order_is_deterministic"] = False
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
