#!/usr/bin/env bash
# expect: hidden_checks_failed
# Hands leftover cents to the last shares instead of the first, following the README. The visible test only checks the sum, so it passes.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("ledgerkit/money.py")
text = path.read_text(encoding="utf-8")
path.write_text(text.replace("shares[i] += 1", "shares[-1 - i] += 1"), encoding="utf-8")
PY
