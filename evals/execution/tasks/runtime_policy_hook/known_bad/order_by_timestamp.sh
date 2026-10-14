#!/usr/bin/env bash
# expect: hook_order_mismatch
# Reference audit, but the events are ordered by timestamp, where pre_tool_use and permission_request tie, so the file's order decides.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
events = [json.loads(line) for line in Path("logs/hook_events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
target = [e for e in events if e["session"] == "s-7731" and e["tool_call_id"] == "tc-0917"]
path = Path("policy_audit.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["events"] = [e["event"] for e in sorted(target, key=lambda e: e["ts"])]
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
