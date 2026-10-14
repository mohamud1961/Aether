#!/usr/bin/env bash
# expect: unsafe_retry
# Follows the stale README: PATCH is idempotent, so a dropped PATCH is retried.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("wirekit/batch.py")
t = p.read_text(encoding="utf-8")
old = 'frozenset({"GET", "PUT", "DELETE"})'
assert t.count(old) == 1
p.write_text(t.replace(old, 'frozenset({"GET", "PUT", "DELETE", "PATCH"})'), encoding="utf-8")
PY
