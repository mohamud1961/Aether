#!/usr/bin/env bash
# expect: handoff_contract_missing
# Writes the agent loader and frontmatter sections correctly, then stops; the placeholder handoff stays.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
path = Path("subagent_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["agents_loaded"] = ["research-auditor", "support-runner"]
audit["agent_order_is_deterministic"] = True
audit["frontmatter_summary"] = {
    "research-auditor": {"background": True, "hooks_retained": True, "mcp_servers_retained": ["qa-server", "inline-probe"], "permission_mode": "plan", "skills_retained": ["alpha-skill", "citation-helper"]},
    "support-runner": {"background": False, "hooks_retained": False, "mcp_servers_retained": ["qa-server", "ticket-api"], "permission_mode": "default", "skills_retained": []},
}
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
