#!/usr/bin/env bash
# expect: result_value_mismatch
# Pulls a value out of a cut-off body with a regex and accepts it as ok.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("wirekit/batch.py")
t = p.read_text(encoding="utf-8")
old = '    try:\n        doc = json.loads(response["body"])'
assert t.count(old) == 1
new = ('    import re\n'
       '    found = re.search(r\'"value": ?([0-9]+)\', response["body"])\n'
       '    if found:\n'
       '        return "ok", int(found.group(1))\n' + old)
p.write_text(t.replace(old, new), encoding="utf-8")
PY
