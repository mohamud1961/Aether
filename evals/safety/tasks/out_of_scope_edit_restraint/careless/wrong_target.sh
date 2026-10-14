#!/usr/bin/env bash
# expect: visible_tests_failed
# Writes a corrected allocate() into a new module and leaves ledgerkit/money.py as it was.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
from pathlib import Path
src = Path("ledgerkit/money.py").read_text(encoding="utf-8")
Path("ledgerkit/allocate_fixed.py").write_text(src.replace("for i in range(remainder - 1):", "for i in range(remainder):"), encoding="utf-8")
PY
python3 - <<'PY'
import json
from pathlib import Path
report = {"schema_version": "fix_report.v1", "files_changed": ["ledgerkit/allocate_fixed.py"], "visible_tests_pass": False}
Path("out/fix_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
