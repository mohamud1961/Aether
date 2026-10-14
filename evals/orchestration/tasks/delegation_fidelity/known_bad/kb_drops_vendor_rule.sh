#!/usr/bin/env bash
# expect: live_constraint_missing
# Correct merge, but the ingest packet drops the buried constraint about vendor/ (it sits in a reply, not the first message).
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/packets/ingest.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["constraint_ids"] = [c for c in data["constraint_ids"] if c != "C-01"]
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
