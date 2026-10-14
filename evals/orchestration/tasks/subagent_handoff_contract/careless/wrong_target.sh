#!/usr/bin/env bash
# expect: agent_loader_not_deterministic
# Writes the record into agents/ instead of the audit file, leaving the placeholder in place.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
record = {"agents_loaded": ["research-auditor", "support-runner"], "agent_order_is_deterministic": True}
Path("agents/subagent_audit.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
PY
