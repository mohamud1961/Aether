#!/usr/bin/env bash
# Writes the correct final state into the current directory's config.json.
set -euo pipefail
cat > config.json <<'JSON'
{
  "service": "orders",
  "port": 8080,
  "log_level": "info",
  "shutdown_timeout_s": 30
}
JSON
