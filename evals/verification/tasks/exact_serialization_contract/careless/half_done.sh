#!/usr/bin/env bash
# expect: balance_precision_mismatch
# Converts the current export, but copies balances straight from the CSV text (1234.5, 7).
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import csv, json
from pathlib import Path
export = json.loads(Path("data/EXPORTS.json").read_text())["current_export"]
rows = sorted(csv.DictReader(Path(export).open(encoding="utf-8", newline="")), key=lambda r: int(r["id"]))
parts = []
for r in rows:
    tags = [t for t in r["tags"].split(",") if t]
    parts.append("  {\n    \"id\": %d,\n    \"name\": %s,\n    \"balance\": %s,\n    \"active\": %s,\n    \"tags\": [%s]\n  }" % (
        int(r["id"]), json.dumps(r["name"]), r["balance"].strip(), "true" if r["active"] == "true" else "false",
        ", ".join(json.dumps(t) for t in tags)))
Path("out/canonical.json").write_text("[\n" + ",\n".join(parts) + "\n]\n", encoding="utf-8")
PY
