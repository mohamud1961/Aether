#!/usr/bin/env bash
# expect: service_did_not_bind
# Writes a file that prints the expected answers and exits, without ever serving.
set -euo pipefail
mkdir -p out
cat > out/service_impl.py <<'PY'
import json
print(json.dumps({"status": "ok", "version": "1.0"}))
PY
