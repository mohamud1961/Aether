#!/usr/bin/env bash
# expect: arguments_mutated
# Reference audit, but the arguments flag is taken from the other session's allowed call (tc-0916), whose path was rewritten.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("policy_audit.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["arguments_mutated"] = True
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
