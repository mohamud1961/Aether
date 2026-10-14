#!/usr/bin/env bash
# expect: stale_ids_mismatch
# Leaves rejected_stale_ids empty, so the stale and superseded rows are never rejected explicitly.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/final_submission.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["rejected_stale_ids"] = []
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
