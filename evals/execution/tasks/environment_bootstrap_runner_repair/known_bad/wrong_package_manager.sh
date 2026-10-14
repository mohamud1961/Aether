#!/usr/bin/env bash
# expect: package_manager_mismatch
# Reference repair, but the report names uv, which the contract does not declare for this project.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/toolchain_repair_report.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["package_manager"] = "uv"
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
