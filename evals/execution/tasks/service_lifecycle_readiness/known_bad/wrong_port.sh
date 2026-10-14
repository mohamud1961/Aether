#!/usr/bin/env bash
# expect: service_did_not_bind
# Binds to 18920, the port in the superseded notes, so nothing answers on the contract port 18923.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("out/service_impl.py")
text = path.read_text(encoding="utf-8")
assert text.count("PORT = 18923") == 1
path.write_text(text.replace("PORT = 18923", "PORT = 18920"), encoding="utf-8")
PY
