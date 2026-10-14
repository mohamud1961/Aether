#!/usr/bin/env bash
# expect: service_crashed_before_second_observation
# Answers the first probes, then exits 1 about 0.1 s after the echo response, before the 2 second window ends.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path

path = Path("out/service_impl.py")
text = path.read_text(encoding="utf-8")
marker = '            self._send_json({"echo": raw})'
if text.count(marker) != 1:
    raise SystemExit("reference file changed: echo response line not found once")
text = text.replace(
    marker,
    marker + "\n            threading.Timer(0.1, os._exit, (1,)).start()",
)
text = text.replace("import json\n", "import json\nimport os\n", 1)
path.write_text(text, encoding="utf-8")
PY
