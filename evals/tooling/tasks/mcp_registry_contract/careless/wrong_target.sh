#!/usr/bin/env bash
# expect: missing_audit_file
# Moves the bundle files into out/ instead of the workspace root, where the registry checks look.
set -euo pipefail
mkdir -p out
mv mcp_audit.json mcp_registry_trace.json out/
