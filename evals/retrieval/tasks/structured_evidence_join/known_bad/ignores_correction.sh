#!/usr/bin/env bash
# expect: late_set_mismatch
# Reference state, except the shipment_corrected event is ignored, so O-1002 keeps its original 11:10Z ship time and counts as late.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
p = Path("out/late_shipments.json")
data = json.loads(p.read_text())
data["late_orders"].insert(0, {"order_id": "O-1002", "promised_at_utc": "2026-10-03T10:00:00Z",
                               "shipped_at_utc": "2026-10-03T11:10:00Z", "delay_minutes": 70})
data["late_orders"].sort(key=lambda x: x["order_id"])
p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
PY
