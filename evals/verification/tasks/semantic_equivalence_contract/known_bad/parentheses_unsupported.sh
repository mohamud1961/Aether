#!/usr/bin/env bash
# expect: expression_evaluation_error
# Starts from the reference and removes the parenthesis rule, so any "(" raises.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("out/solution.py")
text = path.read_text(encoding="utf-8")
old = 'if token == "(":'
assert text.count(old) == 1
path.write_text(text.replace(old, 'if token == "#":'), encoding="utf-8")
PY
