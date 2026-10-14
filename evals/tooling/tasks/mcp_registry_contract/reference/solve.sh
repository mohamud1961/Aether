#!/usr/bin/env bash
# Derives the MCP registry bundle from the sources under mcp/ and the challenge token, and writes
# mcp_audit.json and mcp_registry_trace.json into the current directory.
set -euo pipefail
python3 - <<'PY'
import json
import re
from pathlib import Path

root = Path(".")
SCALAR = {"string", "integer", "number", "boolean"}


def load(rel):
    return json.loads((root / rel).read_text(encoding="utf-8"))


def qualified(server, tool):
    return f"mcp__{server}__{tool}"


def map_schema(schema):
    """Return normalized parameters, or None when the schema does not map."""
    if schema.get("type") != "object" or not isinstance(schema.get("properties"), dict):
        return None
    properties = {}
    for name, spec in schema["properties"].items():
        if not isinstance(spec, dict) or spec.get("type") not in SCALAR:
            return None
        properties[name] = {"type": spec["type"]}
    params = {"type": "object", "properties": properties}
    if "required" in schema:
        params["required"] = schema["required"]
    if "additionalProperties" in schema:
        params["additionalProperties"] = schema["additionalProperties"]
    return params


registry = load("mcp/registry.json")
listings = {}   # qualified name -> number of registry entries listing it
discovered = {}  # qualified name -> (manifest dir, schema path) for active entries
rejected = []
for entry in registry["entries"]:
    manifest = load(entry["manifest"])
    base = Path(entry["manifest"]).parent
    for tool in manifest["tools"]:
        if not tool.get("enabled"):
            continue
        name = qualified(manifest["server"], tool["name"])
        listings[name] = listings.get(name, 0) + 1
        if entry["status"] != "active":
            continue
        schema = load((base / tool["schema"]).as_posix())
        if map_schema(schema) is None:
            rejected.append(name)
        else:
            discovered[name] = (base / tool["schema"]).as_posix()

reasons = load("mcp/reason_codes.json")["outcomes"]
discovered_names = sorted(n for n in discovered)
first = discovered_names[0]
parameters = map_schema(load(discovered[first]))
repeat = sorted(n for n, count in listings.items() if count > 1)
schema_issue_codes = sorted({reasons["schema_mapping"]} if rejected else set())

hooks = load("mcp/hooks/hooks.json")
events = [h["event"] for h in hooks["hooks"] if h.get("enabled")]
policy_path = next(h["policy"] for h in hooks["hooks"] if h["event"] == "permission_request")
policy = load(policy_path)
tool_short = first.split("__")[-1]
behavior = next((r["behavior"] for r in policy["rules"] if r["tool"] == tool_short), policy["default_behavior"])

runs = [json.loads(line) for line in (root / "mcp/runs/runs.ndjson").read_text(encoding="utf-8").splitlines() if line.strip()]
latest = max(runs, key=lambda r: r["started"])
native = latest["results"]

token = (root / "challenge.txt").read_text(encoding="utf-8").strip()
spec = load("mcp/bundle_spec.json")

discovery = {
    "discovered_tool_names": discovered_names,
    "repeat_discovered_tool_names": repeat,
    "schema_issue_reason_codes": schema_issue_codes,
}
schema_mapping = {"qualified_name": first, "parameters": parameters}
invocation_results = {
    "success_reason_code": reasons["success"],
    "timeout_reason_code": reasons["timeout"],
    "error_reason_code": reasons["error"],
    "unavailable_reason_code": reasons["unavailable"],
    "schema_mapping_reason_code": reasons["schema_mapping"],
}
hook_permission_trace = {"events": events, "permission_behavior": behavior}
native_regression = {
    "write_file_exit_code": native["write_file"]["exit_code"],
    "read_file_exit_code": native["read_file"]["exit_code"],
    "read_stdout_contains": native["read_file"]["checked_token"],
}
bundle_contract = {"required_files": spec["required_files"], "trace_file": spec["trace_file"]}
challenge_response = f"payload={token}"

audit = {
    "discovery": discovery,
    "schema_mapping": schema_mapping,
    "invocation_results": invocation_results,
    "hook_permission_trace": hook_permission_trace,
    "native_regression": native_regression,
    "bundle_contract": bundle_contract,
    "challenge_response": challenge_response,
}
trace = {key: audit[key] for key in spec["trace_sections"]}
(root / "mcp_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(root / "mcp_registry_trace.json").write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
