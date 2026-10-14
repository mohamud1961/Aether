#!/usr/bin/env bash
# expect: unsafe_retry
# Fixes the rate-limit handling and the budget, then stops before the idempotency rule.
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
p = Path("wirekit/batch.py")
t = p.read_text(encoding="utf-8")
t = t.replace("MAX_ATTEMPTS = 3", "MAX_ATTEMPTS = 4")
old = '            if response["status"] == 429:\n                failed.append(op_id)\n                break\n'
assert t.count(old) == 1
t = t.replace(old, '            if response["status"] == 429:\n                attempts.append({"op_id": op_id, "attempt": number, "classification": "rate_limited"})\n                continue\n')
p.write_text(t, encoding="utf-8")
PY
