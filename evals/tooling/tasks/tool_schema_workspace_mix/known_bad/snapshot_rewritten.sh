#!/usr/bin/env bash
# expect: other_file_modified
# Deletes the superseded TK-8823 rows from the live snapshot so a naive reader would pick the right ticket.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

path = Path("data/live_snapshot.ndjson")
rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
rows = [r for r in rows if r["ticket_id"] != "TK-8823"]
path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
PY
