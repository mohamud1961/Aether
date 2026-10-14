"""Fixture job: starts a grandchild that sleeps, runs for the given seconds, then reports its token."""
import json
import os
import subprocess
import sys
import time

token, seconds, pid_dir = sys.argv[1], float(sys.argv[2]), sys.argv[3]
started = time.time()
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
with open(os.path.join(pid_dir, token + ".pids"), "w", encoding="utf-8") as handle:
    handle.write(f"{os.getpid()} {child.pid}")
time.sleep(seconds)
child.kill()
child.wait()
print(json.dumps({"token": token, "start": started, "end": time.time()}), flush=True)
