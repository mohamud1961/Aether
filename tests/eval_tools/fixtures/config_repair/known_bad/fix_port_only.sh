#!/usr/bin/env bash
# expect: log_level_not_info
# Fixes port (integer 8080) and leaves log_level as "WARN".
set -euo pipefail
cat > config.json <<'JSON'
{
  "service": "orders",
  "port": 8080,
  "log_level": "WARN",
  "shutdown_timeout_s": 30
}
JSON
