#!/usr/bin/env bash
# expect: shutdown_timeout
# Serves correctly, but calls server.shutdown() directly in the signal handler, as the scaffold does. It runs on the serving thread and never returns.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("out/service_impl.py")
text = path.read_text(encoding="utf-8")
old = "        threading.Thread(target=server.shutdown, daemon=True).start()"
assert text.count(old) == 1
path.write_text(text.replace(old, "        server.shutdown()"), encoding="utf-8")
PY
