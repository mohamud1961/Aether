#!/usr/bin/env bash
# expect: fatal_retried
# Correct policy, but a fatal reply is treated as a transient error and retried.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("wirekit/batch.py")
t = p.read_text(encoding="utf-8")
old = '            if label == "fatal":\n                failed.append(op_id)\n                break\n'
assert t.count(old) == 1
p.write_text(t.replace(old, ""), encoding="utf-8")
PY
