#!/usr/bin/env bash
# expect: row_value_mismatch
# A row written with the old transform (email not lower-cased) survives in the output.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
import json
from pathlib import Path
p = Path("data/output/users_v2.jsonl")
out = []
for line in p.read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    if row["user_id"] == 5:
        row["email"] = row["email"].upper()
    out.append(json.dumps(row, sort_keys=True, ensure_ascii=False))
p.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
