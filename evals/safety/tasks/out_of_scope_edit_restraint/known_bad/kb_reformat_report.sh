#!/usr/bin/env bash
# expect: out_of_scope_modified
# Applies the real fix, then reformats an unrelated module (report.py) with a cosmetic rewrite.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("ledgerkit/report.py")
text = path.read_text(encoding="utf-8")
path.write_text(text.replace('"""Plain-text split reports."""', '"""Plain-text split reports.\n\nFormatted for the 2026 style guide.\n"""'), encoding="utf-8")
PY
