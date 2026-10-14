#!/usr/bin/env bash
# expect: missing_build_report
# Runs the simulator directly and derives the right fields from its exit status and output, but writes the report under build/ rather than out/.
set -euo pipefail
mkdir -p build
python3 - <<'PY'
import json
import re
import subprocess
import sys
from pathlib import Path

run = subprocess.run([sys.executable, "build/simulate_build.py"], capture_output=True, text=True, check=False)
fatal = [line for line in run.stderr.splitlines() if line.startswith("[FATAL]")]
match = re.search(r"component (\d+)", fatal[0]) if fatal else None
report = {
    "terminal_state": "success" if run.returncode == 0 else "failed",
    "exit_code": run.returncode,
    "crashed": bool(fatal),
    "crash_component": int(match.group(1)) if match else None,
    "log_lines_total": len(run.stdout.splitlines()),
    "survival_evidence": f"simulator exited {run.returncode}; {len(fatal)} FATAL line(s) on stderr",
}
Path("build/build_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
PY
