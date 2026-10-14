#!/usr/bin/env bash
# expect: record_count_mismatch
# Renders from the stale data/records.csv snapshot (five rows, Eve active, Bob 10.00), in the right format, and never checks the export pointer.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import csv, json
from decimal import Decimal
from pathlib import Path
rows = sorted(csv.DictReader(Path("data/records.csv").open(encoding="utf-8", newline="")), key=lambda r: int(r["id"]))
blocks = []
for r in rows:
    tags = [t for t in r["tags"].split(",") if t]
    blocks.append("\n".join([
        "  {",
        f'    "id": {int(r["id"])},',
        f'    "name": {json.dumps(r["name"])},',
        f'    "balance": {Decimal(r["balance"]).quantize(Decimal("0.01"))},',
        f'    "active": {"true" if r["active"] == "true" else "false"},',
        f'    "tags": [' + ", ".join(json.dumps(t) for t in tags) + "]",
        "  }",
    ]))
Path("out/canonical.json").write_text("[\n" + ",\n".join(blocks) + "\n]\n", encoding="utf-8")
PY
