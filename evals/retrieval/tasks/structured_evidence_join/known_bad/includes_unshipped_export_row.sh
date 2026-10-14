#!/usr/bin/env bash
# expect: late_set_mismatch
# Reference state plus O-1010, which the export marks shipped but no event log shows as shipped.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
p = Path("out/late_shipments.json")
data = json.loads(p.read_text())
data["late_orders"].append({"order_id": "O-1010", "promised_at_utc": "2026-10-07T16:00:00Z",
                            "shipped_at_utc": "2026-10-07T16:30:00Z", "delay_minutes": 30})
p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
PY
