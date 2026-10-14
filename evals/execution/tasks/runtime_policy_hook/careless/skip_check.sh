#!/usr/bin/env bash
# expect: arguments_mutated
# Takes the first session and the first trace record in the logs, and never checks which call the audit is about.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
events = [json.loads(line) for line in Path("logs/hook_events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
calls = [json.loads(line) for line in Path("logs/tool_calls.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
first_session = events[0]["session"]
order = [e["event"] for e in sorted((e for e in events if e["session"] == first_session), key=lambda e: e["seq"])]
call = calls[0]
audit = {
    "events": order,
    "denied_observation_visible": call["observation_to_model"]["delivered"] is True,
    "denied_action_mutated_workspace": call["fs_digest_before"] != call["fs_digest_after"],
    "arguments_mutated": call["args_before_hooks"] != call["args_after_hooks"],
}
Path("policy_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
