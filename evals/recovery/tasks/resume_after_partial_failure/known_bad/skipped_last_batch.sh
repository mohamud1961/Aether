#!/usr/bin/env bash
# expect: missing_row
# Writes batches 1 to 3 and skips batch 4, so rows 25 to 30 are never written.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("data/output/users_v2.jsonl")
lines = p.read_text(encoding="utf-8").splitlines()
p.write_text("\n".join(lines[:24]) + "\n", encoding="utf-8")
PY
