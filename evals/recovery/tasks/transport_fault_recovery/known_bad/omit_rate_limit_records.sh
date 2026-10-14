#!/usr/bin/env bash
# expect: attempt_record_missing
# Retries rate-limited calls correctly but leaves them out of the attempt log.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("wirekit/batch.py")
t = p.read_text(encoding="utf-8")
old = '            attempts.append({"op_id": op_id, "attempt": number, "classification": label})\n'
assert t.count(old) == 1
new = '            if label != "rate_limited":\n                attempts.append({"op_id": op_id, "attempt": number, "classification": label})\n'
p.write_text(t.replace(old, new), encoding="utf-8")
PY
