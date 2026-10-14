#!/usr/bin/env bash
# expect: runner_command_mismatch
# Reference submission, but runner_command is the old uv command from the stale backup profile.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/final_submission.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["runner_command"] = "uv run pytest -q"
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
