#!/usr/bin/env bash
# Runs the simulator directly, keeps stdout and stderr apart, and writes the report from what the
# process returned and printed. The CI wrapper is not used: its exit status is the status of tail.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
import re
import subprocess
import sys
from pathlib import Path

run = subprocess.run([sys.executable, "build/simulate_build.py"], capture_output=True, text=True, check=False)
stdout_lines = run.stdout.splitlines()
fatal = [line for line in run.stderr.splitlines() if line.startswith("[FATAL]")]
crash_component = None
if fatal:
    match = re.search(r"component (\d+)", fatal[0])
    crash_component = int(match.group(1)) if match else None
report = {
    "terminal_state": "success" if run.returncode == 0 else "failed",
    "exit_code": run.returncode,
    "crashed": bool(fatal),
    "crash_component": crash_component,
    "log_lines_total": len(stdout_lines),
    "survival_evidence": (
        f"simulator exited {run.returncode}; {len(fatal)} FATAL line(s) on stderr"
        + (f" naming component {crash_component}" if crash_component is not None else "")
        + f"; {len(stdout_lines)} lines on stdout"
    ),
}
Path("out/build_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
PY
