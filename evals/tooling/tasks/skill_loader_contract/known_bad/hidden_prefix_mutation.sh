#!/usr/bin/env bash
# expect: hidden_prompt_mutation_detected
# Reports an implicit prefix mutation the loader config does not allow.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

path = Path("skill_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["hidden_behavior"]["implicit_prefix_mutation"] = True
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
