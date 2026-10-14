#!/usr/bin/env bash
# Derives the subagent audit from agents/, skills/, mcp/ and handoff/ and writes subagent_audit.json here.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path

root = Path(".")


def parse_value(raw):
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def frontmatter(path):
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines[0].strip() != "---":
        return None
    close = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    fields = {}
    for line in lines[1:close]:
        key, _, value = line.partition(":")
        fields[key.strip()] = parse_value(value.strip())
    return fields


# Loader: retired agents are skipped; the rest are returned sorted by name.
agents = {}
for path in sorted(root.joinpath("agents").glob("*.md")):
    fields = frontmatter(path)
    if fields is None or fields.get("status") == "retired":
        continue
    agents[fields["name"]] = fields
loaded = sorted(agents)

registry = {s["name"]: s for s in json.loads((root / "mcp/servers.json").read_text(encoding="utf-8"))["servers"]}
skills_on_disk = {p.parent.name for p in root.glob("skills/*/SKILL.md")}

frontmatter_summary = {}
resolved_skills, skill_issues = set(), set()
resolved_mcp, mcp_issues = set(), set()
for name in loaded:
    spec = agents[name]
    names = []
    for entry in spec.get("mcpServers", []):
        if isinstance(entry, dict):
            names.append(entry["name"])
            mcp_issues.add("agent_inline_mcp_unresolved")
        else:
            names.append(entry)
            if entry in registry and registry[entry].get("enabled"):
                resolved_mcp.add(entry)
            else:
                mcp_issues.add("required_mcp_server_missing")
    for skill in spec.get("skills", []):
        if skill in skills_on_disk:
            resolved_skills.add(skill)
        else:
            skill_issues.add("skill_not_found")
    frontmatter_summary[name] = {
        "background": spec.get("background") is True,
        "hooks_retained": len(spec.get("hooks", [])) > 0,
        "mcp_servers_retained": names,
        "permission_mode": spec.get("permissionMode"),
        "skills_retained": spec.get("skills", []),
    }

packet = json.loads((root / "handoff/task_packet.json").read_text(encoding="utf-8"))
fields = ["objective", "scope", "files_to_touch", "ownership", "exit_criteria", "evidence_expectations"]
task_packet = {f: bool(packet.get(f)) for f in fields}

report = json.loads((root / "handoff/worker_report.json").read_text(encoding="utf-8"))
handoff = {
    "status": report["status"],
    "files_changed": bool(report.get("files_changed")),
    "validation_commands": bool(report.get("validation_commands")),
    "external_state": bool(report.get("external_state", {}).get("touched")),
    "unresolved_risks": bool(report.get("unresolved_risks")),
}

inbox = json.loads((root / "handoff/parent_inbox.json").read_text(encoding="utf-8"))
background = [n for n in loaded if agents[n].get("background") is True]
visibility = {
    "parent_visible_unresolved_risks": sorted(inbox.get("risks_surfaced", [])) == sorted(report.get("unresolved_risks", [])) and bool(report.get("unresolved_risks")),
    "no_silent_background_execution": all(n in inbox.get("background_runs_reported", []) for n in background),
}

audit = {
    "agents_loaded": loaded,
    "agent_order_is_deterministic": True,
    "frontmatter_summary": frontmatter_summary,
    "resolution_summary": {
        "resolved_skills": sorted(resolved_skills),
        "skill_issue_reason_codes": sorted(skill_issues),
        "resolved_mcp_servers": sorted(resolved_mcp),
        "mcp_issue_reason_codes": sorted(mcp_issues),
    },
    "task_packet": task_packet,
    "handoff": handoff,
    "visibility": visibility,
}
(root / "subagent_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
