#!/usr/bin/env bash
# expect: key_order_mismatch
# Reference values, but each object writes "active" before "balance".
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
import json
from decimal import Decimal
from pathlib import Path
data = json.loads(Path("out/canonical.json").read_text(encoding="utf-8"), parse_float=Decimal)
lines = ["["]
parts = []
for r in data:
    body = [f'    "id": {r["id"]}', f'    "name": {json.dumps(r["name"])}', f'    "active": {str(r["active"]).lower()}',
            f'    "balance": {r["balance"]}', f'    "tags": [' + ", ".join(json.dumps(t) for t in r["tags"]) + "]"]
    parts.append("  {\n" + ",\n".join(body) + "\n  }")
Path("out/canonical.json").write_text("[\n" + ",\n".join(parts) + "\n]\n", encoding="utf-8")
PY
