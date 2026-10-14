#!/usr/bin/env bash
# expect: port_not_integer_8080
# Fixes log_level ("info") and leaves port as the string "8080".
set -euo pipefail
cat > config.json <<'JSON'
{
  "service": "orders",
  "port": "8080",
  "log_level": "info",
  "shutdown_timeout_s": 30
}
JSON
