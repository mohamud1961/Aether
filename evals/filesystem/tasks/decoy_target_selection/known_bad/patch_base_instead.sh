#!/usr/bin/env bash
# expect: effective_timeout_mismatch
# Writes timeout 300 into beta's base.yaml instead of the production overlay that wins over it, and reports base.yaml as the target.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
cp "$TASK_ROOT/workspace/services/beta/overrides/production.yaml" services/beta/overrides/production.yaml
python3 - <<'PY'
import json
import re
from pathlib import Path
base = Path("services/beta/base.yaml")
base.write_text(re.sub(r"(?m)^timeout:.*$", "timeout: 300", base.read_text(encoding="utf-8")), encoding="utf-8")
path = Path("out/final_submission.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["patched_target"] = "services/beta/base.yaml"
data["effective_timeout_s"] = 300
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
