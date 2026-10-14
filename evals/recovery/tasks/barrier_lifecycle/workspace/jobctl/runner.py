"""Background job runner. Draft from the 2026-10 review; not yet correct."""
import subprocess


class Job:
    def __init__(self, name, exit_code, output):
        self.name = name
        self.exit_code = exit_code
        self.output = output


class JobRunner:
    def __init__(self):
        self.deliveries = []

    def start(self, name, argv):
        # Draft: runs the job to completion here, so jobs never overlap.
        proc = subprocess.run(argv, capture_output=True, text=True)
        return Job(name, proc.returncode, proc.stdout)

    def cancel(self, job):
        # Draft: nothing to signal, the job has already finished.
        pass

    def join(self, job, timeout=None):
        result = {"name": job.name, "exit_code": job.exit_code, "output": job.output, "cancelled": False}
        self.deliveries.append(result)
        return result
