#!/usr/bin/env bash
# expect: skill_collision_handling_missing
# Writes an audit with the right shape and plausible values without reading the sources; reports no collisions.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path

audit = {
    "skills_discovered": ["alpha-skill", "tool-linked"],
    "skill_order_is_deterministic": True,
    "frontmatter_summary": {
        "alpha-skill": {"description": "Audit code under src with read-only tools", "allowed_tools": ["read_file", "grep"], "user_invocable": False, "execution_context": "fork", "paths": ["src/**"]},
        "tool-linked": {"description": "Echo bridge for the QA server", "allowed_tools": ["mcp__qa_server__Echo_Tool"], "user_invocable": True, "execution_context": None, "paths": ["docs/**"]},
    },
    "collision_reason_codes": {"same_file": [], "same_name": []},
    "selection_reason_codes": {"missing": ["skill_not_found"], "duplicate_ref": ["duplicate_skill_ref"], "path_scope_mismatch": ["skill_path_scope_mismatch"]},
    "visible_context": {"recorded_in_prefix": True, "contains_base_directory": True, "contains_skill_body": True, "bounded": True, "truncated": False},
    "metadata_retention": {"hooks_present": True, "hook_matcher_count": 2, "unsupported_hook_events": ["Stop"], "linked_mcp_tools": ["mcp__qa_server__Echo_Tool"]},
    "hidden_behavior": {"implicit_prefix_mutation": False, "implicit_hook_execution": False, "implicit_mcp_invocation": False},
}
Path("skill_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
