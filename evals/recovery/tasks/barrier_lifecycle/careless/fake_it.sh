#!/usr/bin/env bash
# expect: cancel_not_effective
# Writes a runner that reports plausible results without starting any process.
set -euo pipefail
cat > jobctl/runner.py <<'PYEOF'
"""Job runner."""
import json


class Job:
    def __init__(self, name):
        self.name = name


class JobRunner:
    def __init__(self):
        self.deliveries = []

    def start(self, name, argv):
        return Job(name)

    def cancel(self, job):
        return None

    def join(self, job, timeout=None):
        result = {"name": job.name, "exit_code": 0, "cancelled": False,
                  "output": json.dumps({"token": job.name, "start": 0, "end": 0})}
        self.deliveries.append(result)
        return result
PYEOF
