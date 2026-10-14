#!/usr/bin/env bash
# expect: effective_timeout_mismatch
# Sets the production overlay to 3000, which contains "timeout: 300" as a prefix, and claims 300.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("services/beta/overrides/production.yaml")
path.write_text(path.read_text(encoding="utf-8").replace("timeout: 300", "timeout: 3000"), encoding="utf-8")
PY
