#!/usr/bin/env bash
# expect: orphaned_process
# Cancel signals only the job's own pid, so the processes it started keep running.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("jobctl/runner.py")
t = p.read_text(encoding="utf-8")
old = "            os.killpg(job.proc.pid, signal.SIGKILL)\n"
assert t.count(old) == 1
p.write_text(t.replace(old, "            os.kill(job.proc.pid, signal.SIGKILL)\n"), encoding="utf-8")
PY
