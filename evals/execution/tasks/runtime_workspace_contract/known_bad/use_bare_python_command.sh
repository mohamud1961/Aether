#!/usr/bin/env bash
# expect: python_command_mismatch
# Reference submission, but python_command is the bare "python" from the stale notes.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/final_submission.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["python_command"] = "python"
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
