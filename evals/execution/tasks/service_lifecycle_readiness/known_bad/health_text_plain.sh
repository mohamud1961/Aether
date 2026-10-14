#!/usr/bin/env bash
# expect: health_content_type_mismatch
# Serves the correct JSON body for GET /health, but labels it text/plain, as the 2025 notes and the 1.0 echo did.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("out/service_impl.py")
text = path.read_text(encoding="utf-8")
old = "        if self.path == \"/health\":\n            self._send_json(HEALTH_BODY)"
assert text.count(old) == 1
new = (
    "        if self.path == \"/health\":\n"
    "            body = json.dumps(HEALTH_BODY).encode(\"utf-8\")\n"
    "            self.send_response(200)\n"
    "            self.send_header(\"Content-Type\", \"text/plain\")\n"
    "            self.send_header(\"Content-Length\", str(len(body)))\n"
    "            self.end_headers()\n"
    "            self.wfile.write(body)"
)
path.write_text(text.replace(old, new), encoding="utf-8")
PY
