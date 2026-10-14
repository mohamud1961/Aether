#!/usr/bin/env bash
# expect: bundle_field_mismatch
# Reconciles everything, then writes the closure ticket from the stale postmortem draft into the bundle.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
import json
from pathlib import Path
p = Path("artifacts/recovery/final/recovery_bundle.json")
b = json.loads(p.read_text())
b["closure_ticket"] = "RCV-2026-318"
p.write_text(json.dumps(b, indent=2, sort_keys=True) + "\n")
PY
