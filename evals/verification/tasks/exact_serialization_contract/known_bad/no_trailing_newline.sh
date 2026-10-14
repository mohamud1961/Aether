#!/usr/bin/env bash
# expect: formatting_mismatch
# Reference values, but the final newline is dropped.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 -c "from pathlib import Path; p=Path('out/canonical.json'); p.write_text(p.read_text().rstrip('\n'))"
