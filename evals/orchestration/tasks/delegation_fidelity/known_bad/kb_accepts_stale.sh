#!/usr/bin/env bash
# expect: stale_result_accepted
# Correct packets, but the merge takes the reconcile result built on packet version 1 and its finding.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/merged.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["accepted_workers"] = ["ingest", "reconcile", "writer"]
data["rejected"] = []
data["findings"] = sorted(data["findings"] + ["REC-001"])
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
