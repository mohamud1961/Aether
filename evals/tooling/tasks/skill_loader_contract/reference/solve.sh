#!/usr/bin/env bash
# Derives the skill loader audit from skills/ and loader/, and writes skill_audit.json into the current directory.
set -euo pipefail
python3 - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path(".")
config = json.loads((root / "loader/config.json").read_text(encoding="utf-8"))
request = json.loads((root / "loader/request.json").read_text(encoding="utf-8"))


def parse(text):
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, None
    try:
        close = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, None
    fields = {}
    for line in lines[1:close]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        raw_value = value.strip()
        try:
            fields[key.strip()] = json.loads(raw_value)
        except ValueError:
            fields[key.strip()] = raw_value
    return fields, "\n".join(lines[close + 1:]).strip("\n")


discovered = []      # (name, fields, body, rel dir)
collisions_same_file = []
collisions_same_name = []
seen_bytes = {}
seen_names = set()
for path in sorted(root.joinpath(config["discovery_root"]).rglob("SKILL.md"), key=lambda p: p.relative_to(root).as_posix()):
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    fields, body = parse(text)
    if fields is None:
        continue
    digest = hashlib.sha256(raw).hexdigest()
    if digest in seen_bytes:
        collisions_same_file.append("duplicate_skill_realpath")
        continue
    name = fields["name"]
    if name in seen_names:
        collisions_same_name.append("skill_name_collision")
        continue
    seen_bytes[digest] = path
    seen_names.add(name)
    discovered.append((name, fields, body, path.parent.relative_to(root).as_posix()))

by_name = {name: (fields, body, base) for name, fields, body, base in discovered}
ref_counts = {}
for ref in request["references"]:
    ref_counts[ref] = ref_counts.get(ref, 0) + 1
missing = sorted({ref for ref in ref_counts if ref not in by_name})
duplicate_refs = sorted({ref for ref, count in ref_counts.items() if count > 1 and ref in by_name})
scope_mismatch = []
resolved = []
for ref in ref_counts:
    if ref not in by_name:
        continue
    fields, body, base = by_name[ref]
    resolved.append(ref)
    for touched in request["touched_paths"]:
        if not any(Path(touched).match(pattern) for pattern in fields.get("paths", [])):
            scope_mismatch.append(ref)
            break

block = "\n\n".join(f"Base directory: {base}\n{body}" for ref in resolved for _, body, base in [by_name[ref]])
max_chars = config["max_context_chars"]
supported = set(config["supported_hook_events"])
hook_events = [h["event"] for _, fields, _, _ in discovered for h in fields.get("hooks", [])]
linked = sorted({tool for _, fields, _, _ in discovered for tool in fields.get("mcp", [])})

audit = {
    "skills_discovered": [name for name, _, _, _ in discovered],
    "skill_order_is_deterministic": True,
    "frontmatter_summary": {
        name: {
            "description": fields["description"],
            "allowed_tools": fields["allowed-tools"],
            "user_invocable": fields["user-invocable"],
            "execution_context": fields["context"],
            "paths": fields["paths"],
        }
        for name, fields, _, _ in discovered
    },
    "collision_reason_codes": {
        "same_file": sorted(set(collisions_same_file)),
        "same_name": sorted(set(collisions_same_name)),
    },
    "selection_reason_codes": {
        "missing": ["skill_not_found"] if missing else [],
        "duplicate_ref": ["duplicate_skill_ref"] if duplicate_refs else [],
        "path_scope_mismatch": ["skill_path_scope_mismatch"] if scope_mismatch else [],
    },
    "visible_context": {
        "recorded_in_prefix": bool(config["record_context_in_prefix"]),
        "contains_base_directory": all(f"Base directory: {by_name[r][2]}" in block for r in resolved),
        "contains_skill_body": all(by_name[r][1] in block for r in resolved),
        "bounded": isinstance(max_chars, int),
        "truncated": len(block) > max_chars,
    },
    "metadata_retention": {
        "hooks_present": bool(hook_events),
        "hook_matcher_count": sum(len(fields.get("hooks", [])) for _, fields, _, _ in discovered),
        "unsupported_hook_events": sorted({e for e in hook_events if e not in supported}),
        "linked_mcp_tools": linked,
    },
    "hidden_behavior": {
        "implicit_prefix_mutation": config["prefix_mutation"] != "none",
        "implicit_hook_execution": bool(config["run_hooks"]),
        "implicit_mcp_invocation": bool(config["invoke_mcp"]),
    },
}
(root / "skill_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
