#!/usr/bin/env bash
# expect: echo_response_mismatch
# Returns valid JSON for POST /echo, but under the key "echoed" instead of "echo".
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("out/service_impl.py")
text = path.read_text(encoding="utf-8")
assert text.count('self._send_json({"echo": raw})') == 1
path.write_text(text.replace('self._send_json({"echo": raw})', 'self._send_json({"echoed": raw})'), encoding="utf-8")
PY
