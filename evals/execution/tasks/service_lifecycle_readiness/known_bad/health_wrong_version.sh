#!/usr/bin/env bash
# expect: health_response_mismatch
# Serves the right shape with version "1.1" instead of the contract value "1.0".
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path
path = Path("out/service_impl.py")
text = path.read_text(encoding="utf-8")
assert text.count('"version": "1.0"') == 1
path.write_text(text.replace('"version": "1.0"', '"version": "1.1"'), encoding="utf-8")
PY
