#!/usr/bin/env bash
# expect: record_count_mismatch
# Renders the first CSV it finds under data/ (the stale records.csv, five rows) and never checks the pointer.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import csv, json
from decimal import Decimal
from pathlib import Path
rows = sorted(csv.DictReader(Path("data/records.csv").open(encoding="utf-8", newline="")), key=lambda r: int(r["id"]))
out = []
for r in rows:
    tags = [t for t in r["tags"].split(",") if t]
    out.append({"id": int(r["id"]), "name": r["name"], "balance": Decimal(r["balance"]), "active": r["active"] == "true", "tags": tags})
text = "[\n" + ",\n".join("  {\n" + ",\n".join(f'    "{k}": ' + (("[" + ", ".join(json.dumps(t) for t in v) + "]") if k == "tags" else (json.dumps(v) if k in ("name",) else ("true" if v is True else "false" if v is False else str(v)))) for k, v in o.items()) + "\n  }" for o in out) + "\n]\n"
Path("out/canonical.json").write_text(text, encoding="utf-8")
PY
