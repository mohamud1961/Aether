#!/usr/bin/env bash
# expect: result_swapped
# Joins each job with the output of the next job in start order, so handles and results are mismatched.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("jobctl/runner.py")
t = p.read_text(encoding="utf-8")
old = "                output, _ = job.proc.communicate(timeout=timeout)\n"
assert t.count(old) == 1
new = "                partner = self._jobs[(self._jobs.index(job) + 1) % len(self._jobs)]\n                output, _ = partner.proc.communicate(timeout=timeout)\n"
p.write_text(t.replace(old, new), encoding="utf-8")
PY
