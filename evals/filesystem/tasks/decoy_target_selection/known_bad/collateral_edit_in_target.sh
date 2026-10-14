#!/usr/bin/env bash
# expect: target_collateral_edit
# Sets the correct timeout but also changes log_level in the production overlay from warn to info.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("services/beta/overrides/production.yaml")
path.write_text(path.read_text(encoding="utf-8").replace("log_level: warn", "log_level: info"), encoding="utf-8")
PY
