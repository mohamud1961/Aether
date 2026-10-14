#!/usr/bin/env bash
# expect: journal_inconsistent
# Writes the exact output rows, then stops before the journal is brought up to date.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
rows = [json.loads(l) for l in Path("data/input/users.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
out = [json.dumps({"user_id": r["id"], "email": r["email"].strip().lower(),
                   "display_name": " ".join(r["name"].split()), "created_on": r["created"][:10]},
                  sort_keys=True, ensure_ascii=False) for r in rows]
Path("data/output/users_v2.jsonl").write_text("\n".join(out) + "\n", encoding="utf-8")
PY
