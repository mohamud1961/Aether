#!/usr/bin/env bash
# expect: verifier_command_mismatch
# Correct call and receipt, but the summary drops the verifier command.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

path = Path("out/final_submission.json")
candidate = json.loads(path.read_text(encoding="utf-8"))
del candidate["verifier_command"]
path.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
PY
