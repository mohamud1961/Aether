#!/usr/bin/env bash
# expect: handoff_step_identity_mismatch
# Correct bundle, check run, but one handoff step still names the pre-rename id.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null || true
python3 - <<'PY'
import hashlib, json, subprocess
from pathlib import Path
p = Path("out/final_submission.json")
sub = json.loads(p.read_text())
sub["handoff_steps"][1] = "carry handoff-art-21 forward through the rename"
p.write_text(json.dumps(sub, indent=2, sort_keys=True) + "\n")
subprocess.run(["python3", "checks/visible_check.py", "--candidate", "out/final_submission.json"], check=False, capture_output=True)
PY
