#!/usr/bin/env bash
# expect: retracted_constraint_present
# Gives reconcile the rejected live-database ask (X-02) in place of the frozen-snapshot constraint (C-03).
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/packets/reconcile.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["constraint_ids"] = sorted(["C-01", "X-02"])
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
