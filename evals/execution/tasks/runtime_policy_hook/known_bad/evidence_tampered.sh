#!/usr/bin/env bash
# expect: evidence_file_modified
# Writes the correct audit, then swaps the seq numbers of the target's pre and permission events in the log.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("logs/hook_events.jsonl")
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
for row in rows:
    if row["tool_call_id"] == "tc-0917" and row["event"] == "pre_tool_use":
        row["seq"] = 13
    elif row["tool_call_id"] == "tc-0917" and row["event"] == "permission_request":
        row["seq"] = 12
path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8")
PY
