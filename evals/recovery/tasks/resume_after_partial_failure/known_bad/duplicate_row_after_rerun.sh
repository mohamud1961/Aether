#!/usr/bin/env bash
# expect: duplicate_row
# Keeps the uncommitted rows of batch 3 and re-runs the batch on top, so user 17 appears twice.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("data/output/users_v2.jsonl")
lines = p.read_text(encoding="utf-8").splitlines()
lines.insert(20, lines[16])
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
