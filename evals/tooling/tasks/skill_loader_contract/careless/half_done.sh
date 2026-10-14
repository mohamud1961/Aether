#!/usr/bin/env bash
# expect: skill_collision_handling_missing
# Writes the discovered skills and the frontmatter summary, then stops; the stale collision and selection sections stay.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path

path = Path("skill_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["skills_discovered"] = ["alpha-skill", "tool-linked"]
audit["skill_order_is_deterministic"] = True
audit["frontmatter_summary"] = {
    "alpha-skill": {"description": "Audit code under src with read-only tools", "allowed_tools": ["read_file", "grep"], "user_invocable": False, "execution_context": "fork", "paths": ["src/**"]},
    "tool-linked": {"description": "Echo bridge for the QA server", "allowed_tools": ["mcp__qa_server__Echo_Tool"], "user_invocable": True, "execution_context": None, "paths": ["docs/**"]},
}
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
