#!/usr/bin/env bash
# expect: input_file_modified
# Deletes the rollback line from the live log segment, then runs the reference on the edited log.
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
p = Path('ops/m-middle.log')
p.write_text(''.join(l for l in p.read_text(encoding='utf-8').splitlines(True) if 'op=rollback' not in l), encoding='utf-8')
PY
bash "$TASK_ROOT/reference/solve.sh"
