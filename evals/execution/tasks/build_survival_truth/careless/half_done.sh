#!/usr/bin/env bash
# expect: missing_survival_evidence
# Records the terminal fields from a real run, then stops before the line count and the evidence.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
import re
import subprocess
import sys
from pathlib import Path
run = subprocess.run([sys.executable, "build/simulate_build.py"], capture_output=True, text=True)
fatal = [line for line in run.stderr.splitlines() if line.startswith("[FATAL]")]
match = re.search(r"component (\d+)", fatal[0]) if fatal else None
report = {
    "terminal_state": "success" if run.returncode == 0 else "failed",
    "exit_code": run.returncode,
    "crashed": bool(fatal),
    "crash_component": int(match.group(1)) if match else None,
}
Path("out/build_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
PY
