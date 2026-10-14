#!/usr/bin/env bash
# expect: missing_verifier_pass_event
# Makes the correct edit but leaves the verifier command out of the submission.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/final_submission.json")
data = json.loads(path.read_text(encoding="utf-8"))
del data["verifier_command"]
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
