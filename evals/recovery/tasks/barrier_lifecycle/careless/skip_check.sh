#!/usr/bin/env bash
# expect: orphaned_process
# Follows the README: plain Popen, cancel kills the job's pid only, and nothing is checked afterwards.
set -euo pipefail
cat > jobctl/runner.py <<'PYEOF'
"""Job runner (first-draft behaviour from the README)."""
import subprocess


class Job:
    def __init__(self, name, proc):
        self.name = name
        self.proc = proc
        self.cancelled = False


class JobRunner:
    def __init__(self):
        self.deliveries = []

    def start(self, name, argv):
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        return Job(name, proc)

    def cancel(self, job):
        job.cancelled = True
        job.proc.kill()

    def join(self, job, timeout=None):
        output, _ = job.proc.communicate(timeout=timeout)
        result = {"name": job.name, "exit_code": None if job.cancelled else job.proc.returncode,
                  "output": output, "cancelled": job.cancelled}
        self.deliveries.append(result)
        return result
PYEOF
