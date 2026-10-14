#!/usr/bin/env bash
# expect: expression_result_mismatch
# Starts from the reference and makes subtraction right-associative, the withdrawn 0.3 draft, so 10-3-2 gives 9.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("out/solution.py")
text = path.read_text(encoding="utf-8")
old = 'value = value + right if op == "+" else value - right'
assert text.count(old) == 1
path.write_text(text.replace(old, 'value = value + right if op == "+" else right - value'), encoding="utf-8")
PY
