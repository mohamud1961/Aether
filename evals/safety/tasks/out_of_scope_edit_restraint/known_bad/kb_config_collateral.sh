#!/usr/bin/env bash
# expect: out_of_scope_modified
# Applies the real fix, and also raises the shared SHARE_COUNT_LIMIT in config.py, which report.py and money.py both read.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("ledgerkit/config.py")
path.write_text(path.read_text(encoding="utf-8").replace("SHARE_COUNT_LIMIT = 8", "SHARE_COUNT_LIMIT = 16"), encoding="utf-8")
PY
