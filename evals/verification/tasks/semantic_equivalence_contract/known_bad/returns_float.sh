#!/usr/bin/env bash
# expect: expression_result_mismatch
# Starts from the reference and returns a float, so the value is right but the type is not int.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("out/solution.py")
text = path.read_text(encoding="utf-8")
old = "return _Parser(_tokenize(expr)).parse()"
assert text.count(old) == 1
path.write_text(text.replace(old, "return float(_Parser(_tokenize(expr)).parse())"), encoding="utf-8")
PY
