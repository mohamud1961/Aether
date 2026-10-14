#!/usr/bin/env bash
# expect: final_state_value_mismatch
# Runs the reference, then overwrites every key the handoff note lists with its stale value.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

import re
from pathlib import Path
text = Path("ops/handoff/SUMMARY-seq1200.md").read_text(encoding="utf-8")
stale = dict(re.findall(r"^- `([^`]+)`: (\S+)$", text, flags=re.M))
path = Path("out/final_state.json")
state = json.loads(path.read_text(encoding="utf-8"))
state.update({k: v for k, v in stale.items() if k in state})
path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
