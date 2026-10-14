#!/usr/bin/env bash
# expect: agent_frontmatter_parse_mismatch
# Writes an all-true record with plausible names, without reading the agent definitions.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
audit = {
    "agents_loaded": ["research-auditor", "support-runner"],
    "agent_order_is_deterministic": True,
    "frontmatter_summary": {
        "research-auditor": {"background": True, "hooks_retained": True, "mcp_servers_retained": ["qa-server"], "permission_mode": "plan", "skills_retained": ["alpha-skill"]},
        "support-runner": {"background": True, "hooks_retained": True, "mcp_servers_retained": ["qa-server"], "permission_mode": "plan", "skills_retained": ["alpha-skill"]},
    },
    "resolution_summary": {"resolved_skills": ["alpha-skill"], "skill_issue_reason_codes": [], "resolved_mcp_servers": ["qa-server"], "mcp_issue_reason_codes": []},
    "task_packet": {k: True for k in ["objective", "scope", "files_to_touch", "ownership", "exit_criteria", "evidence_expectations"]},
    "handoff": {"status": "complete", "files_changed": True, "validation_commands": True, "external_state": False, "unresolved_risks": False},
    "visibility": {"parent_visible_unresolved_risks": True, "no_silent_background_execution": True},
}
Path("subagent_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
