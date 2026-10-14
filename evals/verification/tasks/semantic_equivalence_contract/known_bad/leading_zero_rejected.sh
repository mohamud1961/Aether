#!/usr/bin/env bash
# expect: expression_evaluation_error
# Starts from the reference and rejects integers with a leading zero, as the legacy notes say, so 007+1 raises.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("out/solution.py")
text = path.read_text(encoding="utf-8")
old = "if token.isdigit():"
assert text.count(old) == 1
path.write_text(text.replace(old, 'if token.isdigit() and not (len(token) > 1 and token[0] == "0"):'), encoding="utf-8")
PY
