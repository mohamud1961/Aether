#!/usr/bin/env bash
# expect: cancel_not_effective
# Makes jobs start and join independently, but leaves cancel as a no-op.
set -euo pipefail
cat > jobctl/runner.py <<'PYEOF'
"""Job runner: start and join work, cancel still to do."""
import subprocess


class Job:
    def __init__(self, name, proc):
        self.name = name
        self.proc = proc
        self.cancelled = False
        self.result = None


class JobRunner:
    def __init__(self):
        self.deliveries = []

    def start(self, name, argv):
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, start_new_session=True)
        return Job(name, proc)

    def cancel(self, job):
        return None

    def join(self, job, timeout=None):
        if job.result is None:
            output, _ = job.proc.communicate(timeout=timeout)
            job.result = {"name": job.name, "exit_code": job.proc.returncode,
                          "output": output, "cancelled": job.cancelled}
            self.deliveries.append(job.result)
        return dict(job.result)
PYEOF
