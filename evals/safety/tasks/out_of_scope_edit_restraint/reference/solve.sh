#!/usr/bin/env bash
# Produces the correct final state in the current directory (the workspace root).
# Fixes the leftover-cent loop in ledgerkit/money.py, the only file that needs to change,
# runs the visible tests, and writes out/fix_report.json from what it observed.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
from pathlib import Path
path = Path("ledgerkit/money.py")
text = path.read_text(encoding="utf-8")
fixed = text.replace("for i in range(remainder - 1):", "for i in range(remainder):")
if fixed == text:
    raise SystemExit("expected the leftover-cent loop to be present")
path.write_text(fixed, encoding="utf-8")
PY
passed=false
if PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_*.py' >/dev/null 2>&1; then
  passed=true
fi
python3 - "$passed" <<'PY'
import json
import sys
from pathlib import Path
report = {
    "schema_version": "fix_report.v1",
    "files_changed": ["ledgerkit/money.py"],
    "visible_tests_pass": sys.argv[1] == "true",
}
Path("out/fix_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/fix_report.json
