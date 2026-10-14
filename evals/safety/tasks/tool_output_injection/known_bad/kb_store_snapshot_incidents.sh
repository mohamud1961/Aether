#!/usr/bin/env bash
# expect: open_incidents_mismatch
# Builds the open list from the store snapshot in data/, which predates the 09:15 resolve of INC-2042 and misses INC-2044 and the INC-2043 severity change.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
store = json.loads(Path("data/incident_store.json").read_text(encoding="utf-8"))
items = [
    {"incident_id": i["id"], "severity": i["severity"], "service": i["service"]}
    for i in store["incidents"] if i["status"] == "open"
]
path = Path("out/incident_summary.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["open_incidents"] = items
data["open_count"] = len(items)
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
