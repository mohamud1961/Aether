#!/usr/bin/env bash
# expect: sibling_killed
# Cancel signals the process group of the most recently started job instead of the one it was given.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("jobctl/runner.py")
t = p.read_text(encoding="utf-8")
old = "            os.killpg(job.proc.pid, signal.SIGKILL)\n"
assert t.count(old) == 1
p.write_text(t.replace(old, "            os.killpg(self._jobs[-1].proc.pid, signal.SIGKILL)\n"), encoding="utf-8")
PY
