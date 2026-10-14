#!/usr/bin/env bash
# expect: missing_survival_evidence
# Reference report with the evidence string cleared.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("out/build_report.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["survival_evidence"] = "  "
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
