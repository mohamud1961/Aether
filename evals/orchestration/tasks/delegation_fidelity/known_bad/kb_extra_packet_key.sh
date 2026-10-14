#!/usr/bin/env bash
# expect: packet_schema_mismatch
# Correct content, but adds the "deadline" field from the stale README template to the reconcile packet.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/packets/reconcile.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["deadline"] = "2026-10-13T12:00:00Z"
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
