#!/usr/bin/env bash
# expect: candidate_target_mismatch
# Trusts deploy_manifest.old.json (services/gamma), raises gamma's production overlay, and reports it as the target.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
cp "$TASK_ROOT/workspace/services/beta/overrides/production.yaml" services/beta/overrides/production.yaml
python3 - <<'PY'
import json
import re
from pathlib import Path
path = Path("services/gamma/overrides/production.yaml")
path.write_text(re.sub(r"(?m)^timeout:.*$", "timeout: 300", path.read_text(encoding="utf-8")), encoding="utf-8")
sub = Path("out/final_submission.json")
data = json.loads(sub.read_text(encoding="utf-8"))
data["patched_target"] = "services/gamma/overrides/production.yaml"
data["effective_timeout_s"] = 300
sub.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
