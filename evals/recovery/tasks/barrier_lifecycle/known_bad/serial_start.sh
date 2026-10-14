#!/usr/bin/env bash
# expect: jobs_not_overlapped
# start waits for the job to finish, so the background jobs run one after another.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("jobctl/runner.py")
t = p.read_text(encoding="utf-8")
old = "        self._jobs.append(job)\n        return job\n"
assert t.count(old) == 1
p.write_text(t.replace(old, "        self._jobs.append(job)\n        job.proc.wait()\n        return job\n"), encoding="utf-8")
PY
