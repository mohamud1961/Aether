#!/usr/bin/env bash
# expect: duplicate_delivery
# Appends to deliveries on every join, so a repeated join delivers the same job again.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("jobctl/runner.py")
t = p.read_text(encoding="utf-8")
old = "        return dict(job.result)\n"
assert t.count(old) == 1
p.write_text(t.replace(old, "        self.deliveries.append(dict(job.result))\n" + old), encoding="utf-8")
PY
