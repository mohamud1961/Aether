#!/usr/bin/env bash
# expect: source_event_mismatch
# Right ticket and workspace, but cites the oldest event (evt-101, priority 3) as the source of the current state.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

path = Path("out/dispatch_plan.json")
plan = json.loads(path.read_text(encoding="utf-8"))
plan["source_event_id"] = "evt-101"
path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
PY
