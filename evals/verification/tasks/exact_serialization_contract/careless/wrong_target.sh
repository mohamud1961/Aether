#!/usr/bin/env bash
# expect: output_missing
# Renders the current export from the pointer into a generic output file name instead of out/canonical.json.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import csv
import json
from decimal import Decimal
from pathlib import Path

export = json.loads(Path("data/EXPORTS.json").read_text(encoding="utf-8"))["current_export"]
rows = sorted(csv.DictReader(Path(export).open(encoding="utf-8", newline="")), key=lambda r: int(r["id"]))
blocks = []
for r in rows:
    balance = Decimal(r["balance"].strip()).quantize(Decimal("0.01"))
    tags = ", ".join(json.dumps(t) for t in r["tags"].split(",") if t)
    blocks.append(
        "  {\n"
        f'    "id": {int(r["id"])},\n'
        f'    "name": {json.dumps(r["name"])},\n'
        f'    "balance": {balance},\n'
        f'    "active": {"true" if r["active"].strip().lower() == "true" else "false"},\n'
        f'    "tags": [{tags}]\n'
        "  }"
    )
Path("out/records.json").write_text("[\n" + ",\n".join(blocks) + "\n]\n", encoding="utf-8")
PY
