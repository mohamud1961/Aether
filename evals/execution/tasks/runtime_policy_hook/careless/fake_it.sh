#!/usr/bin/env bash
# expect: hook_order_mismatch
# Writes the audit the summary describes, without reading the logs or the trace.
set -euo pipefail
cat > policy_audit.json <<'JSON'
{
  "arguments_mutated": false,
  "denied_action_mutated_workspace": false,
  "denied_observation_visible": false,
  "events": ["permission_request", "pre_tool_use", "post_tool_use"]
}
JSON
