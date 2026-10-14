#!/usr/bin/env bash
# expect: unsafe_retry
# Retries dropped and truncated replies for every method, including POST, to be safe about delivery.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("wirekit/batch.py")
t = p.read_text(encoding="utf-8")
old = 'method not in IDEMPOTENT_METHODS:'
assert t.count(old) == 1
p.write_text(t.replace(old, 'False:'), encoding="utf-8")
PY
