#!/usr/bin/env bash
# expect: task_packet_contract_missing
# Marks the packet's scope field as absent although the packet carries it.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
path = Path("subagent_audit.json")
audit = json.loads(path.read_text(encoding="utf-8"))
audit["task_packet"]["scope"] = False
path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
PY
