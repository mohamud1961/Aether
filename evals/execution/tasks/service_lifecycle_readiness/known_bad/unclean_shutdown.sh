#!/usr/bin/env bash
# expect: unclean_shutdown
# Serves correctly and stops on SIGTERM, but exits with status 3 instead of 0.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("out/service_impl.py")
text = path.read_text(encoding="utf-8")
old = "    server.serve_forever()\n    return 0"
assert text.count(old) == 1
path.write_text(text.replace(old, "    server.serve_forever()\n    return 3"), encoding="utf-8")
PY
