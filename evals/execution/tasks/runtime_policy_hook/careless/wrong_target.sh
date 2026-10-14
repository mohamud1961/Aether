#!/usr/bin/env bash
# expect: hook_order_mismatch
# Derives the audit from the logs in hook order, but writes it under reports/ and leaves the top-level policy_audit.json stale.
set -euo pipefail
mkdir -p reports
python3 - <<'PY'
import json
from pathlib import Path

session, call_id = "s-7731", "tc-0917"
events = [json.loads(line) for line in Path("logs/hook_events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
hooks = sorted((e for e in events if e["session"] == session and e["tool_call_id"] == call_id), key=lambda e: e["seq"])
calls = [json.loads(line) for line in Path("logs/tool_calls.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
call = next(c for c in calls if c["session"] == session and c["tool_call_id"] == call_id)
audit = {
    "events": [e["event"] for e in hooks],
    "denied_observation_visible": call["observation_to_model"]["delivered"] is True,
    "denied_action_mutated_workspace": call["fs_digest_before"] != call["fs_digest_after"],
    "arguments_mutated": call["args_before_hooks"] != call["args_after_hooks"],
}
Path("reports/policy_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
