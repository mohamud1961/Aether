#!/usr/bin/env bash
# Produces the correct job runner in the current directory (the workspace root).
# Jobs start without waiting, each in its own session; join reads only that job's pipe;
# cancel signals only that job's process group.
set -euo pipefail
cat > jobctl/runner.py <<'PYEOF'
"""Background job runner: overlapping jobs, per-job joins, cancel by process group."""
import os
import signal
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
        self._jobs = []

    def start(self, name, argv):
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
        )
        job = Job(name, proc)
        self._jobs.append(job)
        return job

    def cancel(self, job):
        if job.result is not None or job.proc.poll() is not None:
            return
        job.cancelled = True
        try:
            os.killpg(job.proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def join(self, job, timeout=None):
        if job.result is None:
            try:
                output, _ = job.proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError(f"{job.name} is still running") from exc
            job.result = {
                "name": job.name,
                "exit_code": None if job.cancelled else job.proc.returncode,
                "output": output,
                "cancelled": job.cancelled,
            }
            self.deliveries.append(job.result)
        return dict(job.result)
PYEOF
python3 checks/visible_check.py
