#!/usr/bin/env bash
# expect: attempt_record_missing
# Writes the fix into a new module that nothing imports and leaves wirekit/batch.py as it was.
set -euo pipefail
cp wirekit/batch.py wirekit/client.py
python3 - <<'PY'
from pathlib import Path
p = Path("wirekit/client.py")
t = p.read_text(encoding="utf-8")
t = t.replace('            attempts.append({"op_id": op_id, "attempt": number, "classification": "dropped"})\n                continue\n',
              '            attempts.append({"op_id": op_id, "attempt": number, "classification": "dropped"})\n                continue\n')
t = t.replace("MAX_ATTEMPTS = 3", "MAX_ATTEMPTS = 4")
t = t.replace('            if response["status"] == 429:\n                failed.append(op_id)\n                break\n',
              '            if response["status"] == 429:\n                attempts.append({"op_id": op_id, "attempt": number, "classification": "rate_limited"})\n                continue\n')
p.write_text(t, encoding="utf-8")
PY
