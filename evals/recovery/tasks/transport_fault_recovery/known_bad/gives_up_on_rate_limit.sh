#!/usr/bin/env bash
# expect: premature_stop
# Treats a 429 as a permanent failure, as the v1 notes said, and stops the operation.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("wirekit/batch.py")
t = p.read_text(encoding="utf-8")
old = '            if label == "ok":\n                results[op_id] = value\n'
assert t.count(old) == 1
new = ('            if label == "rate_limited":\n                failed.append(op_id)\n                break\n' + old)
p.write_text(t.replace(old, new), encoding="utf-8")
PY
