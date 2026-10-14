#!/usr/bin/env bash
# expect: python_command_mismatch
# Writes a plausible submission from the stale notes and the old logs, without resolving the contract.
set -euo pipefail
mkdir -p out
cat > out/final_submission.json <<'JSON'
{
  "python_command": "python",
  "workspace_root": "/workspace/runtime",
  "runner_command": "uv run pytest -q",
  "runtime_classification": "capability_success"
}
JSON
