#!/usr/bin/env bash
# expect: skill_frontmatter_parse_mismatch
# Takes the first alpha-skill it finds under legacy/ as the current skill and never checks the name collision.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path

text = Path("skills/legacy/alpha-skill/SKILL.md").read_text(encoding="utf-8")
header = text.split("---")[1]
fields = {}
for line in header.splitlines():
    if ":" in line:
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
audit = json.loads(Path("skill_audit.json").read_text(encoding="utf-8"))
audit["frontmatter_summary"]["alpha-skill"] = {
    "description": fields["description"],
    "allowed_tools": json.loads(fields["allowed-tools"]),
    "user_invocable": json.loads(fields["user-invocable"]),
    "execution_context": None,
    "paths": json.loads(fields["paths"]),
}
Path("skill_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
