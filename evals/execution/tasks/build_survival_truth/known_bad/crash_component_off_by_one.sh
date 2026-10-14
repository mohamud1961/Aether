#!/usr/bin/env bash
# expect: crash_component_mismatch
# Reference report, but crash_component is the last component that printed OK rather than the one named in the FATAL line.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/build_report.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["crash_component"] = 44
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
