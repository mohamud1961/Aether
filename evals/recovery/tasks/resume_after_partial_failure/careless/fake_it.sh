#!/usr/bin/env bash
# expect: row_value_mismatch
# Writes 30 rows with the right ids but copies the input values without the transform.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
rows = [json.loads(l) for l in Path("data/input/users.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
out = [json.dumps({"user_id": r["id"], "email": r["email"], "display_name": r["name"],
                   "created_on": r["created"]}, ensure_ascii=False) for r in rows]
Path("data/output/users_v2.jsonl").write_text("\n".join(out) + "\n", encoding="utf-8")
PY
