#!/usr/bin/env bash
# expect: malformed_policy_audit
# The audit file exists but is a truncated log line, not a JSON object.
set -euo pipefail
printf '{"events": ["pre_tool_use", "perm' > policy_audit.json
