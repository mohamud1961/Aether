#!/usr/bin/env bash
# expect: attempt_label_mismatch
# Labels a dropped connection as rate_limited in the attempt log (the retry decision is unchanged).
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("wirekit/batch.py")
t = p.read_text(encoding="utf-8")
old = '                label, value = "dropped", None\n'
assert t.count(old) == 1
p.write_text(t.replace(old, '                label, value = "rate_limited", None\n'), encoding="utf-8")
PY
