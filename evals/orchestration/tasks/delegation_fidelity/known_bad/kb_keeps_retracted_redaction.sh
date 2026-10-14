#!/usr/bin/env bash
# expect: retracted_constraint_present
# Correct merge, but the writer packet still carries the PII redaction item that Priya retracted.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/packets/writer.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["constraint_ids"] = sorted(data["constraint_ids"] + ["R-01"])
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
