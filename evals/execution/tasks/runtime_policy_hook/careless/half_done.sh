#!/usr/bin/env bash
# expect: denial_not_visible
# Fixes the event order from the logs, then stops before updating the three flags.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
events = [json.loads(line) for line in Path("logs/hook_events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
target = sorted((e for e in events if e["session"] == "s-7731" and e["tool_call_id"] == "tc-0917"), key=lambda e: e["seq"])
path = Path("policy_audit.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["events"] = [e["event"] for e in target]
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
