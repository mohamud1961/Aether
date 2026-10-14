#!/usr/bin/env bash
# expect: exit_code_mismatch
# Runs the CI wrapper once, takes its exit status and its line count, and never runs the simulator directly.
set -euo pipefail
mkdir -p out
bash build/run_build.sh > build_wrapper_output.txt
status=$?
python3 - "$status" <<'PY'
import json
import sys
from pathlib import Path
status = int(sys.argv[1])
lines = Path("build_wrapper_output.txt").read_text(encoding="utf-8").splitlines()
report = {
    "terminal_state": "success" if status == 0 else "failed",
    "exit_code": status,
    "crashed": any("[FATAL]" in line for line in lines),
    "crash_component": 45,
    "log_lines_total": len(lines),
    "survival_evidence": "CI wrapper exit status and output",
}
Path("out/build_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
PY
rm -f build_wrapper_output.txt
