#!/usr/bin/env bash
# expect: missing_report
# Fixes the defect in ledgerkit/money.py correctly, then stops before writing the report.
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
path = Path("ledgerkit/money.py")
path.write_text(path.read_text(encoding="utf-8").replace("for i in range(remainder - 1):", "for i in range(remainder):"), encoding="utf-8")
PY
