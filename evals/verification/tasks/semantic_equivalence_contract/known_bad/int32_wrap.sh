#!/usr/bin/env bash
# expect: expression_result_mismatch
# Starts from the reference and wraps the result to 32 bits, as the legacy loader did, so large results are wrong.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("out/solution.py")
text = path.read_text(encoding="utf-8")
old = "return _Parser(_tokenize(expr)).parse()"
assert text.count(old) == 1
path.write_text(text.replace(old, "return ((_Parser(_tokenize(expr)).parse() + 2**31) % 2**32) - 2**31"), encoding="utf-8")
PY
