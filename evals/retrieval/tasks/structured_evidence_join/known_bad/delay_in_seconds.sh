#!/usr/bin/env bash
# expect: delay_value_mismatch
# Reference set and times, but delay_minutes holds seconds.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from datetime import datetime
from pathlib import Path
p = Path("out/late_shipments.json")
data = json.loads(p.read_text())
for item in data["late_orders"]:
    a = datetime.fromisoformat(item["shipped_at_utc"].replace("Z", "+00:00"))
    b = datetime.fromisoformat(item["promised_at_utc"].replace("Z", "+00:00"))
    item["delay_minutes"] = int((a - b).total_seconds())
p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
PY
