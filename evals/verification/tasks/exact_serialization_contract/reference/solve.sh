#!/usr/bin/env bash
# Renders the current export named in data/EXPORTS.json to out/canonical.json following spec/format_spec.md.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import csv
import json
from decimal import Decimal
from pathlib import Path

export = json.loads(Path("data/EXPORTS.json").read_text(encoding="utf-8"))["current_export"]
rows = list(csv.DictReader(Path(export).open(encoding="utf-8", newline="")))


def render_tags(raw: str) -> str:
    tags = [tag for tag in raw.split(",") if tag]
    return "[" + ", ".join(json.dumps(tag) for tag in tags) + "]"


blocks = []
for row in sorted(rows, key=lambda item: int(item["id"])):
    balance = Decimal(row["balance"].strip()).quantize(Decimal("0.01"))
    active = "true" if row["active"].strip().lower() == "true" else "false"
    blocks.append(
        "\n".join(
            [
                "  {",
                f'    "id": {int(row["id"])},',
                f'    "name": {json.dumps(row["name"])},',
                f'    "balance": {balance},',
                f'    "active": {active},',
                f'    "tags": {render_tags(row["tags"])}',
                "  }",
            ]
        )
    )
Path("out/canonical.json").write_text("[\n" + ",\n".join(blocks) + "\n]\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/canonical.json
